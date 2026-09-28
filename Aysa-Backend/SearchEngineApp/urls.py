from django.urls import path 
from .views import *
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('product-semantic-search' ,ProductSemanticSearchView.as_view()),
    path('tax-semantic-search' ,TaxSemanticSearchView.as_view()),
    path('ceo-worker-semantic-search' ,CEOWorkerSemanticSearchView.as_view()),

    # GET ALL product margin data 
    path("get-profit-margin-data/", GetProfitMarginData.as_view()),
    path("get-tax-data/", TaxAvenueView.as_view()),
    path("get-ceo-worker-data/", CeoWorkerView.as_view()),

    # URL OF TRACK VISITOR
    path("count-value/", TrackProductSearchCount.as_view()),
    path("create-visitor-value", TrackVisitorCount.as_view()),
    path("get-visitor/", GetVistorView.as_view()),
    path("admin-login", AdminAuthenticationView.as_view()),
    path("auth-check", TokenProtectedView.as_view()),
    path("analysis-table", AnalysisTable.as_view()),
    
    
    # GLOBAL API URLS
    path("global-search", GlobalSearchAPIView.as_view()),
    path("get-data-files", DataFilesSync.as_view()),
    path("train-model", TrainModelView.as_view()),

    ]

if settings.DEBUG == True or settings.DEBUG == False:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

