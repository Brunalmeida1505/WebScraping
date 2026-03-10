"""
Processamento de PDFs do CrazyPatterns
========================================
Lê: db/resultados/crazypatterns_dados.csv
Para cada PDF baixado:
  - Extrai texto completo (receita)
  - Detecta materiais (linhas com palavras-chave)
  - Extrai primeira imagem válida do PDF → salva em downloads/images/crazypatterns_images/
  - Codifica o PDF em base64
Salva:
  - db/resultados/crazypatterns_dados.csv  (atualizado com todas as colunas)
  - db/resultados/crazypatterns_base64.parquet  (com pdf_base64)

Colunas do CSV final:
  titulo, url, materiais, receita, origem,
  pdf_url, pdf_local, pdf_downloaded, pdf_base64,
  imagem_local, imagem_url
"""

import os
import sys
import io
import re
import base64
import pandas as pd
from pathlib import Path

# Fix encoding Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Dependências ──────────────────────────────────────────────────────────────
try:
    import fitz          # PyMuPDF
    from PIL import Image
except ImportError as e:
    print(f"✗ Dependência ausente: {e}")
    print("  Instale com: pip install PyMuPDF Pillow")
    sys.exit(1)

# ── Configurações ─────────────────────────────────────────────────────────────
CSV_IN        = Path("db/resultados/crazypatterns_dados.csv")
CSV_OUT       = Path("db/resultados/crazypatterns_dados.csv")        # mesmo arquivo
PARQUET_OUT   = Path("db/resultados/crazypatterns_base64.parquet")
PDF_DIR       = Path("downloads/pdfs/crazypatterns_pdfs")
IMAGES_DIR    = Path("downloads/images/crazypatterns_images")

MIN_IMG_W     = 150
MIN_IMG_H     = 150
MAX_ASPECT    = 4.0

# Palavras-chave para detectar materiais
MATERIAL_KEYWORDS = [
    "yarn", "hook", "needle", "thread", "wool", "cotton", "acrylic",
    "material", "supplies", "you will need", "what you need",
    "fio", "agulha", "linha", "material", "precisa",
    "garn", "nadel", "häkelnadel",
    "laine", "crochet", "aiguille",
    "hilo", "aguja", "lana",
    "stuffing", "fiberfill", "felt", "eyes", "button", "safety eyes",
    "mm", "weight", "ply", "sport", "worsted", "bulky", "dk",
]

# ── Utilitários ───────────────────────────────────────────────────────────────

def extract_text_from_pdf(doc: fitz.Document) -> str:
    """Extrai texto de todas as páginas do PDF."""
    parts = []
    for page in doc:
        t = page.get_text()
        if t.strip():
            parts.append(t)
    return "\n".join(parts).strip()


def extract_materials(text: str) -> str:
    """
    Detecta linhas de materiais no texto do PDF.
    Retorna string separada por ' | ' ou '' se nenhuma encontrada.
    """
    if not text:
        return ""

    lines = text.splitlines()
    material_lines = []
    in_materials_section = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Linha vazia pode encerrar seção de materiais
            if in_materials_section and len(material_lines) > 2:
                in_materials_section = False
            continue

        lower = stripped.lower()

        # Cabeçalhos de seção de materiais
        if re.match(r"^(materials?|supplies|you.?ll need|what you need|"
                    r"materiais?|materiales?|fournitures?|material(ien)?)\s*:?\s*$",
                    lower):
            in_materials_section = True
            continue

        # Dentro da seção de materiais
        if in_materials_section:
            # Para de coletar se for um novo cabeçalho de seção
            if re.match(r"^(pattern|instructions?|abbreviations?|notes?|"
                        r"receita|instruc|abreviatur|hinweise?|pattern)\s*:?\s*$",
                        lower):
                in_materials_section = False
                continue
            material_lines.append(stripped)
            continue

        # Coleta linhas com palavras-chave de materiais fora de seção explícita
        if any(kw in lower for kw in MATERIAL_KEYWORDS):
            # Evita linhas muito curtas ou muito longas (provavelmente não são materiais)
            if 5 < len(stripped) < 200:
                material_lines.append(stripped)

    # Deduplicar preservando ordem
    seen = set()
    unique = []
    for m in material_lines:
        if m not in seen:
            seen.add(m)
            unique.append(m)

    return " | ".join(unique[:30])   # máx 30 itens


def extract_recipe(text: str) -> str:
    """
    Retorna o texto de instrução do PDF (removendo cabeçalhos de copyright, etc.).
    Limita a 10.000 caracteres.
    """
    if not text:
        return ""

    # Remover linhas típicas de copyright / cabeçalho
    skip_patterns = [
        r"for personal use only",
        r"no commercial use",
        r"copyright",
        r"all rights reserved",
        r"http[s]?://",
        r"www\.",
        r"@",
        r"page \d+",
    ]
    lines = text.splitlines()
    filtered = []
    for line in lines:
        lower = line.lower().strip()
        if any(re.search(p, lower) for p in skip_patterns):
            continue
        filtered.append(line)

    return "\n".join(filtered).strip()[:10_000]


def extract_best_image(doc: fitz.Document, item_id: str, images_dir: Path) -> str:
    """
    Percorre todas as páginas do PDF (até MAX_SCAN_PAGES) e escolhe a
    MAIOR imagem válida por área (w × h), aplicando os filtros:
      - tamanho mínimo: MIN_IMG_W × MIN_IMG_H
      - aspecto máximo: MAX_ASPECT (evita banners/faixas longas)
      - modos suportados: RGB, RGBA, L, CMYK → converte para RGB/JPEG
      - dimensão máxima: MAX_IMG_DIM px no lado maior (redimensiona se necessário)
    Salva o arquivo e retorna o caminho local, ou "" se nada encontrado.
    """
    MAX_SCAN_PAGES = 10      # páginas a varrer
    MAX_IMG_DIM    = 1600    # px máximos no lado maior (evita arquivos enormes)

    best: dict | None = None   # {"xref", "page_num", "img_idx", "area", "ext", "bytes"}

    seen_xrefs: set[int] = set()   # evita processar a mesma imagem referenciada em várias páginas

    n_pages = min(MAX_SCAN_PAGES, len(doc))

    for page_num in range(n_pages):
        page = doc[page_num]
        img_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                base_img = doc.extract_image(xref)
                img_bytes = base_img["image"]
                ext = base_img.get("ext", "jpeg").lower()

                pil = Image.open(io.BytesIO(img_bytes))
                w, h = pil.size

                # Filtro: tamanho mínimo
                if w < MIN_IMG_W or h < MIN_IMG_H:
                    continue

                # Filtro: aspecto (evita logos horizontais e faixas verticais)
                aspect = max(w, h) / max(min(w, h), 1)
                if aspect > MAX_ASPECT:
                    continue

                area = w * h
                if best is None or area > best["area"]:
                    best = {
                        "xref":      xref,
                        "page_num":  page_num,
                        "img_idx":   img_idx,
                        "area":      area,
                        "ext":       ext,
                        "bytes":     img_bytes,
                        "pil":       pil,
                        "mode":      pil.mode,
                    }

            except Exception:
                continue

    if best is None:
        return ""

    # ── Pós-processamento da imagem escolhida ─────────────────────────────────
    pil = best["pil"]
    ext = best["ext"]

    # Converter modos problemáticos → RGB
    if pil.mode == "CMYK":
        pil = pil.convert("RGB")
        ext = "jpeg"
    elif pil.mode == "RGBA":
        # Compor sobre fundo branco
        bg = Image.new("RGB", pil.size, (255, 255, 255))
        bg.paste(pil, mask=pil.split()[3])
        pil = bg
        ext = "jpeg"
    elif pil.mode not in ("RGB", "L"):
        pil = pil.convert("RGB")
        ext = "jpeg"

    # Redimensionar se muito grande
    w, h = pil.size
    if max(w, h) > MAX_IMG_DIM:
        ratio = MAX_IMG_DIM / max(w, h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        pil = pil.resize((new_w, new_h), Image.LANCZOS)

    # Normalizar extensão para jpeg/png
    if ext not in ("jpeg", "jpg", "png"):
        ext = "jpeg"
    save_ext = "jpeg" if ext in ("jpeg", "jpg") else "png"

    fname = f"{item_id}_pdf_p{best['page_num']+1}_{best['img_idx']}.{save_ext}"
    out_path = images_dir / fname

    save_kwargs: dict = {}
    if save_ext == "jpeg":
        save_kwargs = {"format": "JPEG", "quality": 88, "optimize": True}
        if pil.mode != "RGB":
            pil = pil.convert("RGB")
    else:
        save_kwargs = {"format": "PNG", "optimize": True}

    pil.save(out_path, **save_kwargs)
    return str(out_path)
    return ""


def pdf_to_base64(pdf_path: Path) -> str:
    """Lê o PDF e retorna string base64."""
    try:
        with open(pdf_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception as e:
        return ""


def extract_item_id(pdf_local: str) -> str:
    """Extrai o item_id do nome do arquivo PDF (ex: '28415_...' → '28415')."""
    name = Path(pdf_local).stem
    m = re.match(r"^(\d+)", name)
    return m.group(1) if m else name


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  PROCESSAMENTO DE PDFs DO CRAZYPATTERNS")
    print("=" * 70)

    # Criar diretório de imagens
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Carregar CSV
    if not CSV_IN.exists():
        print(f"✗ CSV não encontrado: {CSV_IN}")
        sys.exit(1)

    df = pd.read_csv(CSV_IN, encoding="utf-8-sig")
    print(f"\n📂 CSV carregado: {len(df)} registros")
    print(f"   Colunas: {list(df.columns)}")

    # Garantir colunas novas com dtype string (evita FutureWarning do pandas)
    for col in ["materiais", "receita", "pdf_url", "pdf_base64",
                "imagem_local", "imagem_url"]:
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("").astype(str)

    # Preencher pdf_url a partir da url do item (formato padrão)
    # pdf_url = link de download original (não o zip, mas o link do item de download)
    def make_pdf_url(row):
        if row.get("url") and not pd.isna(row.get("url", "")):
            # Extrair item_id da url
            m = re.search(r"/en/items/(\d+)/", str(row["url"]))
            if m:
                item_id = m.group(1)
                return f"https://www.crazypatterns.net/en/items/free_download/{item_id}"
        return ""

    df["pdf_url"] = df.apply(make_pdf_url, axis=1)

    # Filtrar apenas os com PDF baixado
    df_com_pdf = df[df["pdf_downloaded"] == True].copy()
    total = len(df_com_pdf)
    print(f"\n🗂  {total} PDFs para processar")

    # Verificar quais já têm receita extraída
    ja_processados = df_com_pdf[
        df_com_pdf["receita"].notna() & (df_com_pdf["receita"] != "")
    ]
    print(f"   Já com texto extraído: {len(ja_processados)}")
    print(f"   → Imagens serão RE-EXTRAÍDAS com algoritmo melhorado")

    # Limpar imagens antigas para forçar re-extração com nova lógica
    old_imgs = list(IMAGES_DIR.glob("*_pdf_*"))
    if old_imgs:
        print(f"   → Removendo {len(old_imgs)} imagens antigas para substituir...")
        for p in old_imgs:
            try:
                p.unlink()
            except Exception:
                pass

    processed = 0
    erros = 0
    base64_rows = []   # para o parquet

    for idx, row in df.iterrows():
        if row.get("pdf_downloaded") is not True and row.get("pdf_downloaded") != 1:
            continue

        pdf_local = str(row.get("pdf_local", ""))
        if not pdf_local or pd.isna(row.get("pdf_local")):
            continue

        # Verificar existência do arquivo
        pdf_path = Path(pdf_local)
        if not pdf_path.exists():
            # Tentar relativo ao cwd
            pdf_path = Path(os.getcwd()) / pdf_local
        if not pdf_path.exists():
            print(f"  ⚠ PDF não encontrado: {pdf_local}")
            continue

        item_id = extract_item_id(pdf_local)

        # Pular texto se já processado (tem receita), mas SEMPRE re-extrair imagem
        receita_atual = str(row.get("receita", "")).strip()
        ja_tem_receita = bool(receita_atual and receita_atual not in ("", "nan"))

        processed += 1
        titulo_curto = str(row.get("titulo", ""))[:50]

        try:
            doc = fitz.open(str(pdf_path))

            # ── Texto completo ────────────────────────────────────
            full_text = extract_text_from_pdf(doc)

            # ── Materiais e receita ──────────────────────────────
            if not ja_tem_receita:
                materiais = extract_materials(full_text)
                receita   = extract_recipe(full_text)
                df.at[idx, "materiais"] = materiais
                df.at[idx, "receita"]   = receita

            # ── Imagem do PDF (sempre re-extrai com nova lógica) ─
            img_local = extract_best_image(doc, item_id, IMAGES_DIR)
            if img_local:
                df.at[idx, "imagem_local"] = img_local
                # imagem_url: manter URL remota do site se já existir
                if not str(row.get("imagem_url", "")).strip() or str(row.get("imagem_url", "")).strip() == "nan":
                    df.at[idx, "imagem_url"] = img_local

            # ── Base64 ───────────────────────────────────────────
            b64 = pdf_to_base64(pdf_path)

            base64_rows.append({
                "url":         row.get("url", ""),
                "titulo":      row.get("titulo", ""),
                "pdf_local":   pdf_local,
                "pdf_base64":  b64,
                "origem":      row.get("origem", "CrazyPatterns"),
            })

            doc.close()

            status = "✓"
            print(f"  [{processed}/{total}] {status} {titulo_curto}")

        except Exception as e:
            erros += 1
            print(f"  [{processed}/{total}] ✗ {titulo_curto[:40]} — {e}")

        # Salvar progressivamente a cada 20 itens
        if processed % 20 == 0:
            df.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")

    # ── Salvar CSV final ──────────────────────────────────────────────────────
    # Reordenar colunas
    col_order = [
        "titulo", "url", "materiais", "receita", "origem",
        "pdf_url", "pdf_local", "pdf_downloaded", "pdf_base64",
        "imagem_local", "imagem_url",
    ]
    # Adicionar pdf_base64 no CSV (pode ficar pesado — opcional)
    # Para o CSV principal, deixar pdf_base64 vazio; colocar só no parquet
    df["pdf_base64"] = ""   # limpar do CSV principal
    existing_cols = [c for c in col_order if c in df.columns]
    extra_cols = [c for c in df.columns if c not in col_order]
    df = df[existing_cols + extra_cols]

    df.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")
    print(f"\n✓ CSV salvo: {CSV_OUT}  ({len(df)} registros)")

    # ── Salvar Parquet com base64 ─────────────────────────────────────────────
    if base64_rows:
        df_b64 = pd.DataFrame(base64_rows)
        df_b64.to_parquet(PARQUET_OUT, index=False)
        print(f"✓ Parquet salvo: {PARQUET_OUT}  ({len(df_b64)} registros)")

    # ── Resumo ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESUMO")
    print("=" * 70)
    print(f"  PDFs processados : {processed}")
    print(f"  Erros            : {erros}")

    imgs = list(IMAGES_DIR.glob("*_pdf_*"))
    print(f"  Imagens extraídas: {len(imgs)}")
    if imgs:
        total_mb = sum(p.stat().st_size for p in imgs) / 1_048_576
        print(f"  Tamanho imagens  : {total_mb:.1f} MB")

    com_receita = (df["receita"].notna() & (df["receita"] != "")).sum()
    com_mat     = (df["materiais"].notna() & (df["materiais"] != "")).sum()
    com_img     = (df["imagem_local"].notna() & (df["imagem_local"] != "")).sum()
    total_csv   = len(df)
    print(f"\n  CSV — total       : {total_csv}")
    print(f"  CSV — com receita : {com_receita} ({com_receita/total_csv*100:.0f}%)")
    print(f"  CSV — com mat.    : {com_mat} ({com_mat/total_csv*100:.0f}%)")
    print(f"  CSV — com imagem  : {com_img} ({com_img/total_csv*100:.0f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
