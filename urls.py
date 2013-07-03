from django.conf.urls.defaults import patterns, include, url

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'youtube.views.home', name='home'),
    # url(r'^youtube/', include('youtube.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
	
	(r'^user/(?P<user>\w+)/playlists/(?P<playlist>\w+)/updateplaylist/$', 'playlistlist.views.update_playlist_dets'),
	(r'^user/(?P<user>\w+)/playlists/(?P<playlist>\w+)/edit/$', 'playlistlist.views.create_playlist'),
	(r'^user/(?P<user>\w+)/playlists/(?P<playlist>\w+)$', 'playlistlist.views.playlist_dets'),
	(r'^user/(?P<user>\w+)/playlists/details$', 'playlistlist.views.playlist_dets'),
	(r'^user/(?P<user>\w+)/playlists/$', 'playlistlist.views.playlist_list'),
	(r'^user/(?P<user>\w+)/updateplaylistlist$', 'playlistlist.views.update_playlist_list'),
	(r'^addtoken$', 'playlistlist.views.add_token'),
	('^$', 'playlistlist.views.arrival'),
)
