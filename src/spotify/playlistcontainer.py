'''
Created on 10/04/2011

@author: mikel
'''
import ctypes

from spotify import DuplicateCallbackError, UnknownCallbackError, handle_sp_error, user

from _spotify import playlistcontainer as _playlistcontainer, playlist as _playlist, user as _user

from spotify.utils.decorators import synchronized, extract_args

from spotify.utils.iterators import CallbackIterator

import playlist

from utils.finalize import track_for_finalization
from utils.weakmethod import WeakMethod



class ProxyPlaylistContainerCallbacks:
    _container = None
    _callbacks = None
    _callback_struct = None
    _callback_struct_ptr = None
    
    
    def __init__(self, container, callbacks):
        self._container = container
        self._callbacks = callbacks
        self._callback_struct = _playlistcontainer.callbacks(
            _playlistcontainer.cb_playlist_added(WeakMethod(self._playlist_added)),
            _playlistcontainer.cb_playlist_removed(WeakMethod(self._playlist_removed)),
            _playlistcontainer.cb_playlist_moved(WeakMethod(self._playlist_moved)),
            _playlistcontainer.cb_container_loaded(WeakMethod(self._container_loaded)),
        )
        self._callback_struct_ptr = ctypes.pointer(self._callback_struct)
    
    
    def _playlist_added(self, c_container, c_playlist, position, data):
        self._callbacks.playlist_added(
            self._container, self._container.playlist(position), position
        )
    
    
    def _playlist_removed(self, c_container, c_playlist, position, data):
        self._callbacks.playlist_removed(
            self._container, self._container.playlist(position), position
        )
    
    
    def _playlist_moved(self, c_container, c_playlist, position, new_position, data):
        self._callbacks.playlist_moved(
            self._container, self._container.playlist(position),
            position, new_position
        )
    
    
    def _container_loaded(self, container, data):
        self._callbacks.container_loaded(self._container)
        
    
    def get_struct_ptr(self):
        return self._callback_struct_ptr
    
    
    def get_callbacks(self):
        return self._callbacks



class PlaylistContainerCallbacks:
    def playlist_added(self, container, playlist, position):
        pass
    
    def playlist_removed(self, container, playlist, position):
        pass
    
    def playlist_moved(self, container, playlist, position, new_position):
        pass
    
    def container_loaded(self, container):
        pass



@extract_args
@synchronized
def _finalize_container(container_interface, container_struct):
    container_interface.release(container_struct)
    print "container __del__ called"



class PlaylistContainer:
    __container_struct = None
    __container_interface = None
    
    _manager = None
    
    #Just a shortcut callback to avoid subclassing PlaylistContainerCallbacks
    _onload_callback = None
    
    #Keep references to callbacks structs an the like
    _callbacks = None
    
    
    @synchronized
    def __init__(self, container_struct):
        self.__container_struct = container_struct
        self.__container_interface = _playlistcontainer.PlaylistContainerInterface()
        self._playlist_objects = {}
        self._callbacks = {}
        
        #Register finalizers
        args = (self.__container_interface, self.__container_struct)
        track_for_finalization(self, args, _finalize_container)
    
    
    @synchronized
    def is_loaded(self):
        return self.__container_interface.is_loaded(self.__container_struct)
    
    
    @synchronized
    def add_callbacks(self, callbacks):
        cb_id = id(callbacks)
        if cb_id in self._callbacks:
            raise DuplicateCallbackError()
        
        else:
            proxy = ProxyPlaylistContainerCallbacks(self, callbacks)
            self._callbacks[cb_id] = proxy
            
            self.__container_interface.add_callbacks(
                self.__container_struct, proxy.get_struct_ptr(), None
            )
    
    
    @synchronized
    def remove_callbacks(self, callbacks):
        cb_id = id(callbacks)
        if cb_id not in self._callbacks:
            raise UnknownCallbackError()
        
        else:
            ptr = self._callbacks[cb_id].get_struct_ptr()
            self.__container_interface.remove_callbacks(
                self.__container_struct, ptr, None
            )
            del self._callbacks[cb_id]
    
    
    def remove_all_callbacks(self):
        for key in self._callbacks.keys():
            self.remove_callbacks(self._callbacks[key].get_callbacks())
    
    
    @synchronized
    def num_playlists(self):
        return self.__container_interface.num_playlists(
            self.__container_struct
        )
        
    
    @synchronized
    def playlist(self, pos):
        playlist_struct = self.__container_interface.playlist(
            self.__container_struct, pos
        )
        
        if playlist_struct is not None:
            pi = _playlist.PlaylistInterface()
            pi.add_ref(playlist_struct)
            return playlist.Playlist(playlist_struct)
    
    
    def playlists(self):
        return CallbackIterator(self.num_playlists, self.playlist)
    
    
    @synchronized
    def playlist_type(self, index):
        return self.__container_interface.playlist_type(self.__container_struct, index)
    
    
    @synchronized
    def playlist_folder_name(self, index):
        buf = (ctypes.c_char() * 255)()
        handle_sp_error(
            self.__container_interface.playlist_folder_name(
                self.__container_struct, index, ctypes.byref(buf), 255
            )
        )
        return buf.value
    
    
    @synchronized
    def playlist_folder_id(self, index):
        return self.__container_interface.playlist_folder_id(
            self.__container_struct, index
        )
    
    
    @synchronized
    def add_new_playlist(self, name):
        return playlist.Playlist(
            self.__container_interface.add_new_playlist(
                self.__container_struct, name
            )
        )
    
    
    @synchronized
    def add_playlist(self, link):
        return playlist.Playlist(
            self.__container_interface.add_playlist(
                self.__container_struct, link.get_struct()
            )
        )
    
    
    @synchronized
    def remove_playlist(self, index):
        #FIXME: Should refresh index in _playlist_objects
        handle_sp_error(
            self.__container_interface.remove_playlist(
                self.__container_struct, index
            )
        )
    
    
    @synchronized
    def move_playlist(self, index, new_position, dry_run):
        handle_sp_error(
            self.__container_interface.move_playlist(
                self.__container_struct, new_position, dry_run
            )
        )
    
    
    @synchronized
    def add_folder(self, index, name):
        handle_sp_error(
            self.__container_interface.add_folder(
                self.__container_struct, index, name
            )
        )
    
    
    @synchronized
    def owner(self):
        user_struct = self.__container_interface.owner(
            self.__container_struct
        )
        
        if user_struct is not None:
            ui = _user.UserInterface()
            ui.add_ref(user_struct)
            return user.User(user_struct)
    
    
    def __len__(self):
        return self.num_playlists()
    
    
    def get_struct(self):
        return self.__container_struct
