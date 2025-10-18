from django.core.management.base import BaseCommand
from listings.services.scraper import scrape_listing
from pprint import pprint

class Command(BaseCommand):
    help = "Parse one Krisha.kz listing by URL and print JSON"

    def add_arguments(self, parser):
        parser.add_argument('url')

    def handle(self, *args, **opts):
        data = scrape_listing(opts['url'])
        pprint(data)