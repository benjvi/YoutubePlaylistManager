from django.db import models
import gdata.youtube
import gdata.youtube.service
# Create your models here.

class FilteredUserPlaylistList(models.Model):
	
	user = models.CharField(max_length=200)
	length = models.IntegerField()
	num_included = models.IntegerField()
	num_excluded = models.IntegerField()
	# oauth_token = models.CharField(max_length=200)
	# oauth_token_secret = models.CharField(max_length=200)
	#filtered_playlist_list = raw_playlist list
	# filter according to strings in the title, length of playlist etc
	
	#exluded_playlist_list = list()
	 # holds those playlists that were excluded by the filtering
	
#define my own models based on youtube classes?
	#NOTE to self - all the actions to get specific content should be associated with the views.py , the purpose of which is to return specific page content

class PlaylistPlus(models.Model):
	filtereduserplaylistlist = models.ForeignKey(FilteredUserPlaylistList)
	title = models.CharField(max_length=200)
	isincluded = models.BooleanField()    #this shows whether the playlist is included in the filteredplaylist
	isprivate = models.BooleanField()
	yt_playlistid = models.CharField(max_length=200)
	length = models.IntegerField()			#number of videos
	
class VideoInPlaylist(models.Model):
	title = models.CharField(max_length=200)
	yt_id = models.CharField(max_length=200)		#'normal' url pointing to the video on youtube
	duration = models.IntegerField()       # in seconds
	quality = models.CharField(max_length=200)			# set up a number of CHOICES for this variable
	isalive = models.BooleanField()
	isrestricted = 	models.CharField(max_length=200)		# for videos that have region restrictions, or cant be played on modile devices. Again, CHOICES
	playlistplus = models.ForeignKey(PlaylistPlus)
	position = models.IntegerField()    # position in playlist. The first video has a value 1
	
class MyOAuthToken(models.Model):
	key = models.CharField(max_length=200)
	secret = models.CharField(max_length=200)
	filtereduserplaylistlist = models.ForeignKey(FilteredUserPlaylistList)