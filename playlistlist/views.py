# Create your views here.
from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.conf import settings
from gdata import youtube
from gdata.youtube.service import YouTubeService
from playlistlist.models import FilteredUserPlaylistList, PlaylistPlus, VideoInPlaylist, MyOAuthToken
from time import sleep
import re
import gdata.auth
import gdata.base.service
import datetime as dt
import random

def add_token(request):
	#set the scope to yt API
	yt_scope = gdata.service.lookup_scopes('youtube')
	#gd_client = gdata.base.service.GBaseService()
	gd_client = YouTubeService()
	gd_client.SetOAuthInputParameters(
        gdata.auth.OAuthSignatureMethod.HMAC_SHA1,
        settings.GDATA_CREDS['key'],
        consumer_secret=settings.GDATA_CREDS['secret'],
	)
	#need to check the browser for existing tokens - if we have them then just skip this stage and redirect to the users list of playlists - dont want to add duplicates
	if (request.session.has_key('oauth_token_key')):
		#check that this one also exists in the database and is valid
		try:
			#check for user token - search in the database
			my_oauth_token = MyOAuthToken.objects.filter(key=request.session['oauth_token_key'])[0]
			retr_filt_playlist_list = my_oauth_token.filtereduserplaylistlist
		except (MyOAuthToken.DoesNotExist, KeyError):
			1==1  #this page is intended to deal with the case where we dont have a token already!
		else:
			return render_to_response('youtube/listofplaylists.html', {'filt_playlist_list': retr_filt_playlist_list}, context_instance=RequestContext(request))
	
	
	goog_url = ''
	if not (request.GET.has_key('oauth_token')): #we don't have a token yet
        #create a request token with the contacts api scope
		rt = gd_client.FetchOAuthRequestToken(scopes=yt_scope)
        #store the token's secret in a session variable
		request.session['token_secret'] = rt.secret
		#TODO - is this insecure?? 
		        
        #get an authorization URL for our token from gdata
		gd_client.SetOAuthToken(rt)
		goog_url = gd_client.GenerateOAuthAuthorizationURL()+'&oauth_callback='+request.build_absolute_uri()
		return HttpResponseRedirect(goog_url)

	else: #we've been redirected back by google with the auth token as a query parameter
		#create a request token object from the URL (converts the query param into a token object)
		rt = gdata.auth.OAuthTokenFromUrl(url=request.build_absolute_uri())
		
		#set the secret to what we saved above, before we went to Google
		rt.secret = request.session['token_secret']
		
		#then delete from session
		request.session['token_secret'] = ''
		
		#set the scope again
		rt.scopes = yt_scope;
		
		#upgrade our request token to an access token (where the money at)
		at = gd_client.UpgradeToOAuthAccessToken(authorized_request_token=rt)
		
		
		# Here, I want to associate my oauth token and secret with the user currently logged in
		# So, request a feed and get the info from there? I think that you still can't tell the username from what google returns ie the token:
		oauth_input_params = gdata.auth.OAuthInputParams(gdata.auth.OAuthSignatureMethod.HMAC_SHA1, 'anonymous', consumer_secret='anonymous')
		oauth_token = gdata.auth.OAuthToken(key=at.key, secret=at.secret, scopes=yt_scope, oauth_input_params=oauth_input_params)
		gd_client.SetOAuthToken(oauth_token) 
		#This section fetches the (new or updated) information to put in the database
		
		playlistfeed = gd_client.GetYouTubePlaylistFeed(username='default')
		user = playlistfeed.author[0].name.text
		# put in statement to account for case when the feed is not accessible
		
		try:
			retr_filt_playlist_list = FilteredUserPlaylistList.objects.get(user=user)
		
		except (FilteredUserPlaylistList.DoesNotExist):										#expect this to happen for first-time users
			filt_playlist_list = FilteredUserPlaylistList(user=user, length=0, num_included=0, num_excluded=0)
			filt_playlist_list.save()
			oauth_token = MyOAuthToken(key=at.key, secret=at.secret, filtereduserplaylistlist=filt_playlist_list)
			oauth_token.save()
			#we have just associated the token with the currently logged-in user
			
			#instanciate and assign values to playlistlist and playlist objects
			i=0									#for some reason the TotalResults object returns a number larger than the *actual* number of playlists. Maybe there is another attribute I have missed?
			for entry in playlistfeed.entry:
				playlist_tag = re.match(r'##enablist##', entry.title.text)
				if (playlist_tag==None):
					playlistplus = PlaylistPlus(filtereduserplaylistlist=filt_playlist_list, title=entry.title.text, isincluded=True, isprivate=False, yt_playlistid=entry.id.text, length=0)
					#TODO assign the proper values to isincluded, and isprivate, so they can be used in later features
					idlist = re.split('/', playlistplus.yt_playlistid)
					playlistplus.yt_playlistid = idlist[-1]
					playlistplus.save()
					i=i+1
				else:
					continue
			
			filt_playlist_list.length=i
			filt_playlist_list.num_included = i
			filt_playlist_list.save()
			#now we just need to give the user the oauth_token_key so that they will not have to authorize again:
			request.session['oauth_token_key'] = at.key
			
			#set the persistence of this cookie to a long time, for convenience
			expiry_date = dt.datetime(2020, 12, 31)
			request.session.set_expiry(expiry_date)
			
			#redirect to page displaying list of user playlists
			return HttpResponseRedirect('/user/'+user+'/playlists/')
			
		else:
			#if the same user has been authenticated before, then we want to check that their access token is still valid, and give them a cookie with the token key
			#this should occur when the user is using a different browser, or their cookies have been deleted, or become invalid
			#so, we needed them to authenticate again in order to verify their user credentials, but we do not need the new cookie unless the old one has become invalid
			try:
				oauth_token = MyOAuthToken.objects.filter(filtereduserplaylistlist=retr_filt_playlist_list)[0]
				oauth_token_test = gdata.auth.OAuthToken(key=str(oauth_token.key), secret=str(oauth_token.secret), scopes=yt_scope, oauth_input_params=oauth_input_params)
			except(IndexError):
				user_test=user+'not'
				#this SHOULDNT happen - since we found that the user exists as a precondition to go into the parent 'else' clause
			else:
				oauth_token_test = gdata.auth.OAuthToken(key=str(oauth_token.key), secret=str(oauth_token.secret), scopes=yt_scope, oauth_input_params=oauth_input_params)
				gd_client.SetOAuthToken(oauth_token_test) 
				playlistfeed_test = gd_client.GetYouTubePlaylistFeed(username='default')
				user_test = playlistfeed_test.author[0].name.text
			
			if (user_test!=user):		
				#token is broken, so need to use the new token we just retrieved
				oauth_token = MyOAuthToken(key=at.key, secret=at.secret, filtereduserplaylistlist=retr_filt_playlist_list)
				oauth_token.save()
				
				#give the new token to the client, in a cookie
				request.session['oauth_token_key'] = at.key
				#set the persistence of this cookie to a long time, for convenience
				expiry_date = dt.datetime(2020, 12, 31)
				request.session.set_expiry(expiry_date)
			else:
				#gice the client the old cookie again
				request.session['oauth_token_key'] = oauth_token.key
				
			
			#checking for updated playlist details
			try: 
				for j in range(retr_filt_playlist_list.length):
					PlaylistPlus.objects.get(filtereduserplaylistlist=retr_filt_playlist_list, title=playlistfeed.entry[-j].title.text)  		#checks for changes in playlist list
					#since the excluded playlists all currently occur at the start of the list, starting from the end should work
					#TODO check for playlist deletion etc. want better algorithm here!!
					#also, only works for up to 25 playlists, since this is the max # results google will return in one feed query
			except (PlaylistPlus.DoesNotExist, IndexError): 								#corresponding to new playlists being added, (net) playlist deletion
				
				#delete the set of objects associated with the user and the videos associated with each playlist. inefficient but easy method
				
				playlist_set = PlaylistPlus.objects.filter(filtereduserplaylistlist=retr_filt_playlist_list)
				
				for playlistplus in playlist_set:
					video_set = VideoInPlaylist.objects.filter(playlistplus=playlistplus)
					for videoinplaylist in video_set:
						videoinplaylist.delete()
					playlistplus.delete()
				
				#getting the new playlists
				i=0									#for some reason the TotalResults object returns a number larger than the *actual* number of playlists. Maybe there is another attribute I have missed?
				for entry in playlistfeed.entry:
					playlist_tag = re.match(r'##enablist##', entry.title.text)
					if (playlist_tag==None):
						playlistplus = PlaylistPlus(filtereduserplaylistlist=retr_filt_playlist_list, title=entry.title.text, isincluded=True, isprivate=False, yt_playlistid=entry.id.text, length=0)
						#TODO assign the proper values to isincluded, and isprivate, so they can be used in later features
						idlist = re.split('/', playlistplus.yt_playlistid)
						playlistplus.yt_playlistid = idlist[-1]
						playlistplus.save()
						i=i+1
					else:
						continue
				retr_filt_playlist_list.length=i
				retr_filt_playlist_list.num_included = i
				retr_filt_playlist_list.save()	
				return HttpResponseRedirect('/user/'+user+'/playlists/')
			else:
				return HttpResponseRedirect('/user/'+user+'/playlists/')
			
def playlist_list(request, user):
	try:
		#check for user token - search in the database
		my_oauth_token = MyOAuthToken.objects.filter(key=request.session['oauth_token_key'])[0]
		retr_filt_playlist_list = my_oauth_token.filtereduserplaylistlist
	except (MyOAuthToken.DoesNotExist, KeyError):
		#get user to authenticate
		return HttpResponseRedirect(reverse(add_token))
	else:
		return render_to_response('youtube/listofplaylists.html', {'filt_playlist_list': retr_filt_playlist_list}, context_instance=RequestContext(request))
	
	#pass model to template for rendering to page
	#want to get all playlist objects associated with current user and then (ultimately) print them out
	#do thi by passing instanciated filtereduserplaylist model as context - can access the playlist set associated with it

def playlist_dets(request, user, playlist):
	try:
		#check for user token - search in the database
		my_oauth_token = MyOAuthToken.objects.filter(key=request.session['oauth_token_key'])[0]
		filt_list = my_oauth_token.filtereduserplaylistlist
	except (MyOAuthToken.DoesNotExist):
		#get user to authenticate
		return HttpResponseRedirect(reverse(add_token))
	else:
		try:
			sel_playlist = filt_list.playlistplus_set.get(yt_playlistid=request.POST['playlist'])
		except (KeyError, PlaylistPlus.DoesNotExist):
			return HttpResponse("Fail")
		else:
			yt = YouTubeService()
			yt_scope = gdata.service.lookup_scopes('youtube')
			oauth_input_params = gdata.auth.OAuthInputParams(gdata.auth.OAuthSignatureMethod.HMAC_SHA1, 'anonymous', consumer_secret='anonymous')
			oauth_token = gdata.auth.OAuthToken(key=str(request.session['oauth_token_key']), secret=str(my_oauth_token.secret), scopes=yt_scope, oauth_input_params=oauth_input_params)
			yt.SetOAuthToken(oauth_token) 
			try:
					VideoInPlaylist.objects.get(playlistplus=sel_playlist, position=1)
			except (VideoInPlaylist.DoesNotExist):
				# the first time retrieve details for the playlist, need to generate the details to put in the database
				vid_count=0
				for i in range(8):
					j=(25*i)+1;
					playlist_feed = yt.GetYouTubePlaylistVideoFeed(uri='http://gdata.youtube.com/feeds/api/playlists/'+sel_playlist.yt_playlistid+'?start-index='+str(j)+"&amp;v=2") # sel_playlist.yt_playlistid+
					for entry in playlist_feed.entry:
						try:
							vid_id = entry.GetHtmlLink().href
							vid_duration = entry.media.duration.seconds  # this throws an error but returns the right value - I dont know why
						except (AttributeError):
							#when the duration cannot be retrieved, it is because the video is inaccessible (dead) so deal with dead videos here
							#just going to ignore dead videos for now - they will not be entered into the database
							continue
						else:
							vid_count = vid_count+1
							videoinplaylist = VideoInPlaylist(title=entry.title.text, yt_id=str(vid_id), duration=vid_duration, quality ='', isalive=True, isrestricted=False, playlistplus=sel_playlist,  position=vid_count)
							#TODO: populate fields from the youtube data - quality, isalive, isrestricted
							videoinplaylist.save()
							
				
				sel_playlist.length=vid_count
				sel_playlist.save()
				ordered_videos = sel_playlist.videoinplaylist_set.order_by('position')
				return render_to_response('youtube/playlistdetails.html', {'filt_playlist_list': filt_list, 'playlistplus': sel_playlist, 'ordered_videos':ordered_videos}, context_instance=RequestContext(request))
			else:
				up_to_date=True
				
				#TODO - add detecting of when the videos in the playlsit have changed. for now just add the manual option to update the playlist details
				
				if (up_to_date==False):	#corresponding to new playlists being added, (net) playlist deletion
					#delete the set of objects associated with the user and the videos associated with each playlist. inefficient but easy method
					for i in range(sel_playlist.length):
						video = sel_playlist.videoinplaylist_set.get(position=(i+1))
						video.delete()
						
					#getting the new playlists
					vid_count=0
					for i in range(8):
						j=(25*i)+1;
						playlist_feed = yt.GetYouTubePlaylistVideoFeed(uri='http://gdata.youtube.com/feeds/api/playlists/'+sel_playlist.yt_playlistid+'?start-index='+str(j)+"&amp;v=2") # sel_playlist.yt_playlistid+
						for entry in playlist_feed.entry:
							try:
								vid_id = entry.GetHtmlLink().href
								vid_duration = entry.media.duration.seconds  # this throws an error but returns the right value - I dont know why
							except (AttributeError):
								#when the duration cannot be retrieved, it is because the video is inaccessible (dead) so deal with dead videos here
								#just going to ignore dead videos for now - they will not be entered into the database
								continue
							else:
								vid_count = vid_count+1
								videoinplaylist = VideoInPlaylist(title=entry.title.text, yt_id=str(vid_id), duration=vid_duration, quality ='', isalive=True, isrestricted=False, playlistplus=sel_playlist,  position=vid_count)
								#TODO: populate fields from the youtube data - quality, isalive, isrestricted
								videoinplaylist.save()
					sel_playlist.length=vid_count
					sel_playlist.save()
					ordered_videos = sel_playlist.videoinplaylist_set.order_by('position')
					return render_to_response('youtube/playlistdetails.html', {'filt_playlist_list': filt_list, 'playlistplus': sel_playlist, 'ordered_videos':ordered_videos}, context_instance=RequestContext(request))
				
				else:
					ordered_videos = sel_playlist.videoinplaylist_set.order_by('position')
					return render_to_response('youtube/playlistdetails.html', {'filt_playlist_list': filt_list, 'playlistplus': sel_playlist, 'ordered_videos':ordered_videos}, context_instance=RequestContext(request))
				# NB this algorithm is fallible, but should work fine 99.995 of the time - TODO: check

def create_playlist(request, user, playlist):
	try:
		#initialize user lists and youtube service
		try:
			#check for user token - search in the database
			my_oauth_token = MyOAuthToken.objects.filter(key=request.session['oauth_token_key'])[0]
			filt_playlist_list = my_oauth_token.filtereduserplaylistlist
		except (MyOAuthToken.DoesNotExist):
			#get user to authenticate
			return HttpResponseRedirect(reverse(add_token))
		else:
			yt = YouTubeService()
			
			#authenticate youtube service for logged-in user
			yt_scope = gdata.service.lookup_scopes('youtube')
			oauth_input_params = gdata.auth.OAuthInputParams(gdata.auth.OAuthSignatureMethod.HMAC_SHA1, 'anonymous', consumer_secret='anonymous')
			oauth_token = gdata.auth.OAuthToken(key=str(request.session['oauth_token_key']), secret=str(my_oauth_token.secret), scopes=yt_scope, oauth_input_params=oauth_input_params)
			yt.SetOAuthToken(oauth_token)
			sel_playlist = filt_playlist_list.playlistplus_set.get(yt_playlistid=playlist)
			yt.developer_key = ''
		
			#should always have a value of this posted
			sel_videos=request.POST['sel_videos']
	
	except(KeyError):         #put more errors here
		return HttpResponseRedirect(reverse(playlistlist.views.playlist_dets, args=[user, sel_playlist.yt_playlistid]))
		#TODO return error messages to views
	else:
		try:
			shhhh=request.POST['shuffle']
		except(KeyError):
			shuffle=False
		else:
			shuffle=True
			
		#retrieve the last number "sel_videos" of video objects in the selected list (from local database; not a youtube call)
		temp_video_list = list()
		for i in range(int(sel_videos)):
			temp_video = sel_playlist.videoinplaylist_set.get(position=(sel_playlist.length-i))
			temp_video_list.append(temp_video)
		
		#shuffles the playlist if it was checked by the user
		# implement the fisher-Yates shuffle algorithm:
		# swapping each video in turn with another video from a random position in the part of the list that has not yet been passed through (including itself)
		if (shuffle==True):
			for i in range(int(sel_videos)):
				# generate random number between 0 and sel_videos-(i+1)
				ran_num = random.randint(0, int(sel_videos)-(i+1))
				
				temp = temp_video_list[int(sel_videos)-(i+1)]
				temp_video_list[int(sel_videos)-(i+1)] = temp_video_list[ran_num]
				temp_video_list[ran_num] = temp
		
		created_playlist_tag = '##enablist## '
		
		#check if a playlsit already exists. If it does, need to use different code to update rather than create playlist
		#looks for playlist with the same title as the playlist we are about to add
		curr_playlist_feed = yt.GetYouTubePlaylistFeed(username='default')
		playlist_exists=False
		for entry in curr_playlist_feed.entry:
			if (entry.title.text==created_playlist_tag+sel_playlist.title):
				playlist_exists=True
				playlist_uri = entry.id.text
				break
			else:
				continue
		
		response=True
		if (playlist_exists==True):
			#we delete the existing playlist, then continue to add the new playlist
			response = yt.DeletePlaylist(playlist_uri)
			#if deletion is not successful, sets response=False

		if (response==True):
			#create playlist at youtube
			new_private_playlistentry = yt.AddPlaylist(created_playlist_tag+sel_playlist.title, '', True)

			playlist_added=False
			#check that playlist was added successfully
			if isinstance(new_private_playlistentry, gdata.youtube.YouTubePlaylistEntry):
				playlist_added=True

			#retrieve playlist id for newly-added playlist
			new_playlist_id = new_private_playlistentry.id.text	#this is incorrect
			new_playlist_id = new_playlist_id.split('/')[-1]
			new_playlist_feed = 'http://gdata.youtube.com/feeds/api/playlists/'+new_playlist_id

			if (playlist_added == True):
				#add our list of videos to the playlist
				for j in range(int(sel_videos)-1):
					#the ilst is in reverse order, so add videos in reverse
					i = j+1
					temp_video_list[-i].yt_id = temp_video_list[-i].yt_id.split('&')[-2]
					temp_video_list[-i].yt_id = temp_video_list[-i].yt_id.split('=')[-1]
				
					#return HttpResponse('%s %s' % (new_playlist_id, temp_video_list[1].yt_id))
					try:
						playlist_video_entry = yt.AddPlaylistVideoEntryToPlaylist(new_playlist_feed, temp_video_list[-i].yt_id)
					except(gdata.service.RequestError):
						sleep(5)
						try:
							playlist_video_entry = yt.AddPlaylistVideoEntryToPlaylist(new_playlist_feed, temp_video_list[-i].yt_id)
						except(gdata.service.RequestError):
							sleep(15)
							try:
								playlist_video_entry = yt.AddPlaylistVideoEntryToPlaylist(new_playlist_feed, temp_video_list[-i].yt_id)
							except(gdata.service.RequestError):
								return HttpResponse('Youtube is not playing ball right now. Please try again in a minute.')
							else:
								#delete the half-formed playlist created so far - if adding video fails? - no, will get overwritten anyway
								continue
						else:
							#delete the half-formed playlist created so far - if adding video fails? - no, will get overwritten anyway
							continue
					else:
						continue
					sleep(0.5)
				# deal with zero separately. this is a bit hack-y. oh well
				temp_video_list[0].yt_id = temp_video_list[0].yt_id.split('&')[-2]
				temp_video_list[0].yt_id = temp_video_list[0].yt_id.split('=')[-1]
				
				#return HttpResponse('%s %s' % (new_playlist_id, temp_video_list[1].yt_id))
				
				playlist_video_entry = yt.AddPlaylistVideoEntryToPlaylist(new_playlist_feed, temp_video_list[0].yt_id)
				if (isinstance(playlist_video_entry, gdata.youtube.YouTubePlaylistVideoEntry)==False):
					#delete the half-formed playlist created so far - if adding video fails?
					return HttpResponse('Fail.')
				
				#once videos are added, display details of the playlist created - just send to youtube for now
				return HttpResponseRedirect('http://www.youtube.com/playlist?list='+new_playlist_id+'&feature=viewall')
			
			else:
				return HttpResponseRedirect(reverse(playlistlist.views.playlist_dets, args=[user, sel_playlist.yt_playlistid]))
				#TODO return error messages to views
		else:
			return HttpResponseRedirect(reverse(playlistlist.views.playlist_dets, args=[user, sel_playlist.yt_playlistid]))
			#TODO return error messages to views
			
def update_playlist_list(request, user):
	try:
		#initialize user lists and youtube service
		my_oauth_token = MyOAuthToken.objects.get(key=request.session['oauth_token_key'])
		filt_playlist_list = my_oauth_token.filtereduserplaylistlist
	except (MyOAuthToken.DoesNotExist):
		#get user to authenticate
		return HttpResponseRedirect(reverse(add_token))
	else:
		yt = YouTubeService()
		
		#authenticate youtube service for logged-in user
		yt_scope = gdata.service.lookup_scopes('youtube')
		oauth_input_params = gdata.auth.OAuthInputParams(gdata.auth.OAuthSignatureMethod.HMAC_SHA1, 'anonymous', consumer_secret='anonymous')
		oauth_token = gdata.auth.OAuthToken(key=str(request.session['oauth_token_key']), secret=str(my_oauth_token.secret), scopes=yt_scope, oauth_input_params=oauth_input_params)
		yt.SetOAuthToken(oauth_token)
		yt.developer_key = ''
		
		#deleting the original data from the database
		playlist_set = PlaylistPlus.objects.filter(filtereduserplaylistlist=filt_playlist_list)	
		for playlistplus in playlist_set:
			video_set = VideoInPlaylist.objects.filter(playlistplus=playlistplus)
			for videoinplaylist in video_set:
				videoinplaylist.delete()
			playlistplus.delete()
		
		playlistfeed = yt.GetYouTubePlaylistFeed(username='default')
		#getting the new playlists
		i=0									#for some reason the TotalResults object returns a number larger than the *actual* number of playlists. Maybe there is another attribute I have missed?
		for entry in playlistfeed.entry:
			playlist_tag = re.match(r'##enablist##', entry.title.text)
			if (playlist_tag==None):
				playlistplus = PlaylistPlus(filtereduserplaylistlist=filt_playlist_list, title=entry.title.text, isincluded=True, isprivate=False, yt_playlistid=entry.id.text, length=0)
				#TODO assign the proper values to isincluded, and isprivate, so they can be used in later features
				idlist = re.split('/', playlistplus.yt_playlistid)
				playlistplus.yt_playlistid = idlist[-1]
				playlistplus.save()
				i=i+1
			else:
				continue
		
		filt_playlist_list.length=i
		filt_playlist_list.num_included = i
		filt_playlist_list.save()	
		return HttpResponseRedirect('/user/'+user+'/playlists/')
	
def update_playlist_dets(request, user, playlist):
	#initialize user lists and youtube service
	try:
		#initialize user lists and youtube service
		my_oauth_token = MyOAuthToken.objects.get(key=request.session['oauth_token_key'])
		filt_playlist_list = my_oauth_token.filtereduserplaylistlist
	except (MyOAuthToken.DoesNotExist):
		#get user to authenticate
		return HttpResponseRedirect(reverse(add_token))
	else:
		yt = YouTubeService()
		
		#authenticate youtube service for logged-in user
		yt_scope = gdata.service.lookup_scopes('youtube')
		oauth_input_params = gdata.auth.OAuthInputParams(gdata.auth.OAuthSignatureMethod.HMAC_SHA1, 'anonymous', consumer_secret='anonymous')
		oauth_token = gdata.auth.OAuthToken(key=str(request.session['oauth_token_key']), secret=str(my_oauth_token.secret), scopes=yt_scope, oauth_input_params=oauth_input_params)
		yt.SetOAuthToken(oauth_token)
		sel_playlist = filt_playlist_list.playlistplus_set.get(yt_playlistid=playlist)
		yt.developer_key = ''
		
		for i in range(sel_playlist.length):
			video = sel_playlist.videoinplaylist_set.get(position=(i+1))
			video.delete()
			
		#getting the new playlists
		vid_count=0
		for i in range(8):
			j=(25*i)+1;
			playlist_feed = yt.GetYouTubePlaylistVideoFeed(uri='http://gdata.youtube.com/feeds/api/playlists/'+sel_playlist.yt_playlistid+'?start-index='+str(j)+"&amp;v=2") # sel_playlist.yt_playlistid+
			for entry in playlist_feed.entry:
				try:
					vid_id = entry.GetHtmlLink().href
					vid_duration = entry.media.duration.seconds  # this throws an error but returns the right value - I dont know why
				except (AttributeError):
					#when the duration cannot be retrieved, it is because the video is inaccessible (dead) so deal with dead videos here
					#just going to ignore dead videos for now - they will not be entered into the database
					continue
				else:
					vid_count = vid_count+1
					videoinplaylist = VideoInPlaylist(title=entry.title.text, yt_id=str(vid_id), duration=vid_duration, quality ='', isalive=True, isrestricted=False, playlistplus=sel_playlist,  position=vid_count)
					#TODO: populate fields from the youtube data - quality, isalive, isrestricted
					videoinplaylist.save()
		sel_playlist.length=vid_count
		sel_playlist.save()

		ordered_videos = sel_playlist.videoinplaylist_set.order_by('position')
		return render_to_response('youtube/playlistdetails.html', {'filt_playlist_list': filt_playlist_list, 'playlistplus': sel_playlist, 'ordered_videos':ordered_videos}, context_instance=RequestContext(request))
				
def arrival(request):
	return render_to_response('/site_media/index.html')
	