import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import Listing
from .serializers import ListingSerializer
from .services.scraper import scrape_listing
from .services.krisha_scraper import scrape_listing_by_id


class KrishaByIdView(APIView):
    """
    GET /api/krisha/<int:ad_id>
    Возвращает JSON: {title, description, images[], url}
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, ad_id: int):
        try:
            data = scrape_listing_by_id(ad_id)
            # под ваш пример: только нужные ключи
            out = {
                "title": data.get("title") or "",
                "description": data.get("description") or "",
                "images": data.get("images") or [],
                "url": data.get("url"),
            }
            return Response(out, status=status.HTTP_200_OK)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", 502)
            return Response({"detail": f"http error: {e}"}, status=code)
        except Exception as e:
            return Response({"detail": f"scrape failed: {e}"}, status=status.HTTP_502_BAD_GATEWAY)


class IngestView(APIView):
    """
    POST /api/ingest { "url": "https://krisha.kz/a/show/..." }
    """
    def post(self, request):
        url = (request.data.get('url') or '').strip()
        if not url:
            return Response({"detail": "url is required"}, status=400)
        try:
            data = scrape_listing(url)          # ← ТУТ ДЁРГАЕМ ТВОЙ СКРЕЙПЕР
        except Exception as e:
            return Response({"detail": f"scrape failed: {e}"}, status=502)

        # upsert по source_url
        with transaction.atomic():
            obj, created = Listing.objects.select_for_update().get_or_create(
                source_url=url
            )
            # маппинг dict → поля модели
            for f in ('title','price','currency','address','latitude','longitude',
                      'rooms','total_area_m2','living_area_m2','kitchen_area_m2',
                      'floor','floors_total','year_built','description','images'):
                if f in data:
                    setattr(obj, f, data[f])
            obj.raw = data
            obj.save()

        return Response(ListingSerializer(obj).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
