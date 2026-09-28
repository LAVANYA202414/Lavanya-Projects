from django.urls import path,include
from . import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
urlpatterns = [
      # path('save/',views.SaveDAtabase,name='save_random_arrays'),
      path("" , views.home),
      path('input/' ,views.add_new_sequence),
      path('history/' ,views.array_history),
      path('reset/' ,views.Reset_history),
      ]
urlpatterns += staticfiles_urlpatterns()