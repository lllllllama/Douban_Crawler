from _bootstrap import ROOT_DIR  # noqa: F401
from douban_crawler.analysis.data_cleaning import DataCleaner


if __name__ == "__main__":
    cleaner = DataCleaner()
    cleaner.clean()
