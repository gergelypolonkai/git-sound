# -*- coding: utf-8
"""
GUI for git-sound
"""

import sys
import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk
from gi.repository import GLib

from git.exc import InvalidGitRepositoryError
from git import Repo

from .gitmidi import GitMIDI


class GitSoundWindow(object):
    """
    GIU class for git-sound.
    """

    def __init__(self, programs, scales):
        self.__programs = programs
        self.__scales = scales

        self.builder = Gtk.Builder()
        self.builder.add_from_file('git-sound.ui')

        self.win = self.builder.get_object('main-window')
        self.play_button = self.builder.get_object('play-button')
        self.stop_button = self.builder.get_object('stop-button')
        self.vol_spin = self.builder.get_object('vol-spin')
        self.program_combo = self.builder.get_object('program-combo')
        self.progressbar = self.builder.get_object('generate-progress')
        self.branch_combo = self.builder.get_object('branch-combo')
        self.statusbar = self.builder.get_object('statusbar')
        self.pos_label = self.builder.get_object('position-label')
        self.skip_spin = self.builder.get_object('skip-spin')
        self.scale_combo = self.builder.get_object('scale-combo')
        self.chooser_button = self.builder.get_object('repo-chooser')
        self.notelen_spin = self.builder.get_object('notelen-spin')
        self.beatlen_spin = self.builder.get_object('beatlen-spin')
        self.generate_button = self.builder.get_object('generate-button')
        self.save_button = self.builder.get_object('save-button')

        self.gitmidi = None

        program_store = self.builder.get_object('program-list')

        for program_id, program in self.__programs.items():
            program_store.append([program['name'], program_id])

        renderer = Gtk.CellRendererText()
        self.program_combo.pack_start(renderer, True)
        self.program_combo.add_attribute(renderer, "text", 0)

        scale_store = self.builder.get_object('scale-list')

        for scale_id, scale in self.__scales.items():
            scale_store.append([scale[0], scale_id])

        renderer = Gtk.CellRendererText()
        self.scale_combo.pack_start(renderer, True)
        self.scale_combo.add_attribute(renderer, "text", 0)

        self.builder.connect_signals({
            'read_branches': lambda button: self.read_branches(),
            'settings_changed': lambda button: self.settings_changed(),
            'generate_repo': lambda button: self.generate_repo(),
            'play_midi': lambda button: self.play_midi(),
            'stop_midi': lambda button: self.stop_midi(),
            'save_midi': lambda button: self.save_midi(),
        })

        self.win.connect("delete-event", Gtk.main_quit)

    def read_branches(self):
        """
        Callback for the repository chooser. Upon change, this reads
        all the branches from the selected repository.
        """

        # Make sure the Play, Stop and Save buttons are disabled
        self.gitmidi = None
        repo_path = self.chooser_button.get_file().get_path()
        self.branch_combo.remove_all()
        self.branch_combo.set_button_sensitivity(False)
        self.set_buttons_sensitivity(disable_all=True)

        try:
            repo = Repo(repo_path)
        except InvalidGitRepositoryError:
            dialog = Gtk.MessageDialog(
                self.chooser_button.get_toplevel(),
                Gtk.DialogFlags.MODAL,
                Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK,
                "{} is not a valid Git repository".format(
                    repo_path))

            dialog.connect('response',
                           lambda dialog, response_id: dialog.destroy())
            dialog.run()

            return

        self.set_status('Opened repository: {}'.format(repo_path))
        self.branch_combo.set_button_sensitivity(True)

        for head in repo.heads:
            self.branch_combo.append_text(head.name)

    def set_status(self, text):
        """
        Change the status bar text.
        """

        self.statusbar.push(self.statusbar.get_context_id("git-sound"), text)

    def settings_changed(self):
        """
        Callback to use if anything MIDI-related is changed
        (repository, branch, scale or program).
        """

        self.stop_midi()
        self.gitmidi = None
        self.set_buttons_sensitivity()

    def set_buttons_sensitivity(self, disable_all=False):
        """
        Set buttons sensitivity based on different conditions.

        It checks if a repository and a branch is selected or if MIDI
        data is already generated.
        """

        self.stop_button.set_sensitive(False)

        if disable_all:
            self.generate_button.set_sensitive(False)
            self.play_button.set_sensitive(False)
            self.save_button.set_sensitive(False)

            return

        if self.gitmidi is not None:
            self.generate_button.set_sensitive(False)
            self.play_button.set_sensitive(True)
            self.save_button.set_sensitive(True)

            return

        branch_selected = self.branch_combo.get_active_text() is not None
        program_selected = self.program_combo.get_active_id() is not None
        scale_selected = self.scale_combo.get_active_id() is not None

        if branch_selected and program_selected and scale_selected:
            self.generate_button.set_sensitive(True)
            self.play_button.set_sensitive(False)
            self.save_button.set_sensitive(False)

    def generate_repo(self):
        """
        Generate repository data for MIDI data.
        """

        repo_path = self.chooser_button.get_file().get_path()
        branch_selected = self.branch_combo.get_active_text()
        program_selected = self.program_combo.get_active_id()
        scale_selected = self.scale_combo.get_active_id()
        skip = int(self.skip_spin.get_value())
        vol_deviation = int(self.vol_spin.get_value())
        notelen = self.notelen_spin.get_value()
        beatlen = int(self.beatlen_spin.get_value()) or None

        self.progressbar.set_fraction(0.0)
        self.progressbar.pulse()
        self.set_status("Reading commits")
        self.gitmidi = GitMIDI(repository=repo_path,
                               branch=branch_selected,
                               verbose=False,
                               scale=self.__scales[scale_selected][1],
                               program=self.__programs[program_selected],
                               volume_range=vol_deviation,
                               skip=skip,
                               note_duration=notelen,
                               max_beat_len=beatlen)

        self.set_status("Generating beats")
        self.gitmidi.gen_repo_data(callback=self.genrepo_cb)
        self.set_status("Generating MIDI")
        self.gitmidi.generate_midi(callback=self.genrepo_cb)
        self.gitmidi.write_mem()

        self.set_buttons_sensitivity(disable_all=False)

    def genrepo_cb(self, max_count, current):
        """
        Generate repository data. This is called when the user presses
        the Generate button.
        """

        if max_count is None or current is None:
            self.progressbar.pulse()
        else:
            fraction = float(current) / float(max_count)
            self.progressbar.set_fraction(fraction)

        # Make sure the progress bar gets updated
        Gtk.main_iteration_do(False)
        Gtk.main_iteration_do(False)

    def update_play_pos(self):
        """
        Update playback position label.
        """

        if self.gitmidi is None:
            return

        position = self.gitmidi.get_play_pos()

        if position is None:
            self.set_status("Stopped")
            self.pos_label.set_text("0:00")
            self.play_button.set_sensitive(True)
            self.stop_button.set_sensitive(False)

            return False

        position = int(position / 1000)

        minutes = int(position / 60)
        seconds = position - (minutes * 60)

        self.pos_label.set_text("{}:{:02}".format(minutes, seconds))

        return True

    def play_midi(self):
        """
        Start MIDI playback.
        """

        self.set_status(u"Playing…")
        self.gitmidi.play(track=True)
        GLib.timeout_add_seconds(1, self.update_play_pos)
        self.play_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)

    def stop_midi(self):
        """
        Stop MIDI playback.
        """

        if self.gitmidi is not None:
            self.gitmidi.stop()

    def __save(self, dialog, response_id):
        """
        Do the actual MIDI saving after the user chose a file.
        """

        if response_id == Gtk.ResponseType.OK:
            save_file = dialog.get_file().get_path()
            dialog.destroy()
            self.gitmidi.export_file(save_file)

    def save_midi(self):
        """
        Save MIDI data.
        """

        dialog = Gtk.FileChooserDialog(
            u"Save As…",
            self.win,
            Gtk.FileChooserAction.SAVE,
            ("Save", Gtk.ResponseType.OK))
        dialog.set_do_overwrite_confirmation(True)

        dialog.connect('response', self.__save)
        dialog.run()

    def start(self):
        """
        Start the GUI.
        """

        self.win.show_all()
        Gtk.main()

        sys.exit(0)
