from abc import ABC, abstractmethod

class ScraperStrategy(ABC):
    """
    Abstract base class for a web scraper strategy.
    It defines the common interface for all site-specific scrapers.
    """

    def __init__(self, driver):
        self.driver = driver
        self.wait = None

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of the scraper (e.g., 'Circulo', 'Mariskavos')."""
        pass

    @abstractmethod
    def collect_recipe_urls(self) -> set:
        """Collect all recipe URLs from the site."""
        pass

    @abstractmethod
    def extract_recipe_details(self, url: str) -> dict:
        """Extract details from a single recipe URL."""
        pass
    
    @abstractmethod
    def run(self, args: dict):
        """
        The main orchestration method for the scraper.
        This method should implement the full logic of scraping for a specific site,
        including handling arguments like 'force', 'limit', etc.
        """
        pass
