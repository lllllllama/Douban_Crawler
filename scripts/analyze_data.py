from _bootstrap import ROOT_DIR  # noqa: F401
from douban_crawler.analysis.visualization import Analyzer


if __name__ == "__main__":
    analyzer = Analyzer()
    analyzer.analyze()
