from .google_lens import GoogleLensScraper
from .yandex import YandexScraper
from .tineye import TinEyeScraper
from .saucenao import SauceNAOScraper
from .iqdb import IQDBScraper
from .bing_visual import BingVisualScraper
from .ascii2d import ASCII2DScraper
from .baidu import BaiduScraper
from .pinterest import PinterestScraper
from .reddit import RedditScraper

ALL_SCRAPERS = [
    GoogleLensScraper,
    YandexScraper,
    TinEyeScraper,
    SauceNAOScraper,
    IQDBScraper,
    BingVisualScraper,
    ASCII2DScraper,
    BaiduScraper,
    PinterestScraper,
    RedditScraper,
]
