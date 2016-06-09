#! /usr/bin/env python
# -*- coding: utf-8

import argparse
import sys
import os

import shutil

from midiutil.MidiFile import MIDIFile
from StringIO import StringIO
from time import sleep
from git import Repo
from git.objects.blob import Blob
from git.exc import InvalidGitRepositoryError

scales = {
    'c-major': ('C Major', [60, 62, 64, 65, 67, 69, 71]),
    'a-harmonic-minor': ('A Harmonic Minor', [68, 69, 71, 72, 74, 76, 77]),
    'chromatic': ('Chromatic', [60, 61, 62, 63, 64, 65, 66, 67, 68, 69]),
    'pentatonic': ('Pentatonic', [54, 64, 72, 81, 96, 108]),
    'd-major': ('D Major', [62, 64, 65, 67, 69, 71, 72]),
}

programs = {
    'sitar-tablah': {
        'name': 'Sitar and Tablah',
        'commit': {
            'program': 104,
            'octave': -2,
        },
        'file': {
            'program': 115,
            'octave': -1,
        },
    },
    'bells': {
        'name': 'Bells',
        'commit': {
            'program': 14,
            'octave': 0,
        },
        'file': {
            'program': 9,
            'octave': 0,
        },
    },
    'metal': {
        'name': 'Metal',
        'commit': {
            'program': 29,
            'octave': -1,
        },
        'file': {
            'program': 33,
            'octave': -3,
        },
    },
    'pure-violin': {
        'name': 'Violin',
        'commit': {
            'program': 40,
            'octave': 0,
        },
        'file': {
            'program': None,
            'octave': 0,
        },
    },
    'space': {
        'name': 'Space',
        'commit': {
            'program': 94,
            'octave': 1,
        },
        'file': {
            'program': 80,
            'octave': 1,
            'volume': -30,
        },
    },
    'sea-copter': {
        'name': 'Helicopter on the shore',
        'commit': {
            'program': 125,
            'octave': 0,
        },
        'file': {
            'program': 122,
            'octave': 0,
        },
    },
}


def get_file_sha(commit, file_name):
    elements = file_name.split(os.sep)
    t = commit.tree


    while True:
        try:
            t = t[elements.pop(0)]
        except (KeyError, IndexError):
            # The file has been deleted, return the hash of an empty file
            return 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'

        if isinstance(t, Blob):
            break

    return t.hexsha


class GitSoundWindow(object):
    def __init__(self):
        import gi
        gi.require_version('Gtk', '3.0')

        from gi.repository import Gtk
        self.Gtk = Gtk

        from gi.repository import GLib
        self.GLib = GLib

        self.builder = self.Gtk.Builder()
        self.builder.add_from_file('git-sound.ui')

        self.win = self.builder.get_object('main-window')
        self.play_button = self.builder.get_object('play-button')
        self.stop_button = self.builder.get_object('stop-button')

    def read_branches(self, chooser_button):
        self.gitmidi = None
        repo_path = chooser_button.get_file().get_path()
        self.branch_combo.remove_all()
        self.branch_combo.set_button_sensitivity(False)
        self.set_buttons_sensitivity(disable_all=True)

        try:
            repo = Repo(repo_path)
        except InvalidGitRepositoryError:
            dialog = self.Gtk.MessageDialog(
                chooser_button.get_toplevel(),
                self.Gtk.DialogFlags.MODAL,
                self.Gtk.MessageType.ERROR,
                self.Gtk.ButtonsType.OK,
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
        self.statusbar.push(self.statusbar.get_context_id("git-sound"), text)

    def settings_changed(self, button):
        self.gitmidi = None
        self.set_buttons_sensitivity()
        self.stop_midi()

    def set_buttons_sensitivity(self, disable_all=False):
        generate_button = self.builder.get_object('generate-button')
        stop_button = self.builder.get_object('stop-button')
        save_button = self.builder.get_object('save-button')

        if disable_all:
            generate_button.set_sensitive(False)
            self.play_button.set_sensitive(False)
            self.stop_button.set_sensitive(False)
            save_button.set_sensitive(False)

            return

        if self.gitmidi is not None:
            generate_button.set_sensitive(False)
            self.play_button.set_sensitive(True)
            self.stop_button.set_sensitive(False)
            save_button.set_sensitive(True)

            return

        branch_selected = self.branch_combo.get_active_text() is not None
        program_selected = self.program_combo.get_active_id() is not None
        scale_selected = self.scale_combo.get_active_id() is not None

        if branch_selected and program_selected and scale_selected:
            generate_button.set_sensitive(True)
            self.play_button.set_sensitive(False)
            self.stop_button.set_sensitive(False)
            save_button.set_sensitive(False)

    def generate_repo(self, button):
        chooser_button = self.builder.get_object('repo-chooser')
        repo_path = chooser_button.get_file().get_path()
        branch_selected = self.branch_combo.get_active_text()
        program_selected = self.program_combo.get_active_id()
        scale_selected = self.scale_combo.get_active_id()
        skip = int(self.skip_spin.get_value())
        vol_deviation = int(self.vol_spin.get_value())

        self.set_status("Generating data")
        self.progressbar.set_fraction(0.0)
        self.progressbar.pulse()
        self.gitmidi = GitMIDI(repository=repo_path,
                               branch=branch_selected,
                               verbose=False,
                               scale=scales[scale_selected][1],
                               program=programs[program_selected],
                               volume_range=vol_deviation,
                               skip=skip)

        self.gitmidi.gen_repo_data(callback=self.genrepo_cb)
        self.gitmidi.generate_midi(callback=self.genrepo_cb)
        self.gitmidi.write_mem()

        self.set_buttons_sensitivity(disable_all=False)

    def genrepo_cb(self, max_count=None, current=None):
        if max_count is None or current is None:
            self.progressbar.pulse()
        else:
            self.progressbar.set_fraction(current / max_count)

        # Make sure the progress bar gets updated
        self.Gtk.main_iteration_do(False)

    def update_play_pos(self):
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
        self.set_status(u"Playing…")
        self.gitmidi.play(track=True)
        self.GLib.timeout_add_seconds(1, self.update_play_pos)
        self.play_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)

    def stop_midi(self):
        if self.gitmidi is not None:
            self.gitmidi.stop()

    def __save(self, dialog, response_id):
        if response_id == self.Gtk.ResponseType.OK:
            save_file = dialog.get_file().get_path()
            dialog.destroy()
            self.gitmidi.export_file(save_file)

    def save_midi(self):
        dialog = self.Gtk.FileChooserDialog(
            u"Save As…",
            self.win,
            self.Gtk.FileChooserAction.SAVE,
            ("Save", self.Gtk.ResponseType.OK))
        dialog.set_do_overwrite_confirmation(True)

        dialog.connect('response', self.__save)
        dialog.run()

    def start(self):
        program_store = self.builder.get_object('program-list')
        self.program_combo = self.builder.get_object('program-combo')

        for program_id, program in programs.items():
            program_store.append([program['name'], program_id])

        renderer = self.Gtk.CellRendererText()
        self.program_combo.pack_start(renderer, True)
        self.program_combo.add_attribute(renderer, "text", 0)

        scale_store = self.builder.get_object('scale-list')
        self.scale_combo = self.builder.get_object('scale-combo')

        for scale_id, scale in scales.items():
            scale_store.append([scale[0], scale_id])

        renderer = self.Gtk.CellRendererText()
        self.scale_combo.pack_start(renderer, True)
        self.scale_combo.add_attribute(renderer, "text", 0)

        self.branch_combo = self.builder.get_object('branch-combo')
        self.statusbar = self.builder.get_object('statusbar')
        self.pos_label = self.builder.get_object('position-label')
        self.skip_spin = self.builder.get_object('skip-spin')
        self.vol_spin = self.builder.get_object('vol-spin')

        self.builder.connect_signals({
            'read_branches': lambda button: self.read_branches(button),
            'settings_changed': lambda button: self.settings_changed(button),
            'generate_repo': lambda button: self.generate_repo(button),
            'play_midi': lambda button: self.play_midi(),
            'stop_midi': lambda button: self.stop_midi(),
            'save_midi': lambda button: self.save_midi(),
        })

        self.progressbar = self.builder.get_object('generate-progress')

        self.win.connect("delete-event", self.Gtk.main_quit)
        self.win.show_all()
        self.Gtk.main()

        sys.exit(0)


def start_gui():
    win = GitSoundWindow()
    win.start()


class GitMIDI(MIDIFile):
    LOG_CHANNEL = 0
    FILE_CHANNEL = 1

    def __setup_midi(self, track_title=None):
        if self.__verbose:
            print("Preparing MIDI track…")

        if track_title is None:
            # TODO: Change this to something that connects to the repo
            self.addTrackName(0, 0, "Sample Track")

            # TODO: Make this configurable
            self.addTempo(0, 0, 120)

            if self.__need_commits:
                self.addProgramChange(0, self.LOG_CHANNEL,
                                      0, self.__program['commit']['program'])

            if self.__need_files:
                self.addProgramChange(0, self.FILE_CHANNEL,
                                      0, self.__program['file']['program'])

    def __setup_repo(self):
        if self.__verbose:
            print("Analyzing repository…")

        repo = Repo(self.__repo_dir)
        self.branch_head = repo.heads[self.__branch].commit

    def __init__(self,
                 repository='.',
                 branch='master',
                 verbose=False,
                 scale=None,
                 program=None,
                 volume_range=107,
                 skip=0):
        MIDIFile.__init__(self, 1)

        self.__verbose = verbose
        self.__written = False
        self.__repo_dir = repository
        self.__repo = None
        self.__branch = branch
        self.branch_head = None
        self.__repo_data = None
        self.git_log = []
        self.mem_file = StringIO()
        self.__scale = scale
        self.__program = program
        self.__volume_deviation = min(abs(63 - volume_range), 63)
        self.__pygame_inited = False
        self.__playing = False
        self.__skip = skip

        self.__need_commits = self.__program['commit']['program'] is not None
        self.__need_files = self.__program['file']['program'] is not None

        self.__setup_midi()
        self.__setup_repo()

    def gen_volume(self, deletions, insertions, modifier):
        """
        Generate a volume based on the number of modified lines
        (insertions - deletions).

        deviation specifies the minimum and maximum volume (minimum is
        the value of deviation, maximum is 127 - deviation).
        """

        return max(
            self.__volume_deviation,
            min(127 - self.__volume_deviation,
                63 - deletions + insertions + modifier))

    def sha_to_note(self, sha):
        note_num = reduce(lambda res, digit: res + int(digit, 16),
                          list(str(sha)), 0) % len(self.__scale)

        return self.__scale[note_num]

    def gen_beat(self, commit, callback=None):
        stat = commit.stats

        file_notes = []

        for file_name, file_stat in stat.files.items():
            if callback is not None:
                callback(max_count=None, current=None)

            volume_mod = self.__program['file'].get('volume', 0)
            file_notes.append({
                'note': self.sha_to_note(get_file_sha(commit, file_name)) +
                self.__program['file']['octave'] * 12,
                'volume': self.gen_volume(file_stat['deletions'],
                                          file_stat['insertions'],
                                          volume_mod),
            })

        if callback is not None:
            callback(max_count=None, current=None)

        volume_mod = self.__program['commit'].get('volume', 0)

        return {
            'commit_note': self.sha_to_note(commit.hexsha) +
            self.__program['commit']['octave'] * 12,
            'commit_volume': self.gen_volume(stat.total['deletions'],
                                             stat.total['insertions'],
                                             volume_mod),
            'file_notes': file_notes,
        }

    def gen_repo_data(self, force=False, callback=None):
        """
        Populate __repo_data with the Git history data. If force is
        False and the repo_data is already calculated, we do not do
        anything.
        """

        if self.__repo_data and not force:
            return

        if self.__verbose:
            print("Reading repository log…")

        self.__repo_data = []
        counter = 0
        to_process = [self.branch_head]

        while len(to_process) > 0:
            counter += 1

            # TODO: Make this 500 configurable
            if counter % 500 == 0 and self.__verbose:
                print("Done with {} commits".format(counter))

            commit = to_process.pop()

            if callback is not None:
                callback(max_count=None, current=None)

            if not commit in self.__repo_data:
                self.__repo_data.append(commit)
                to_process += commit.parents

        if self.__verbose:
            print("{} commits found".format(counter))
            print("Sorting commits…")

        self.__repo_data.sort(key=lambda commit: commit.authored_date)

        if self.__verbose:
            print("Generating MIDI data…")

        self.git_log = map(
            lambda commit: self.gen_beat(
                commit,
                callback=callback),
            self.__repo_data[self.__skip:])

    @property
    def repo_data(self):
        if self.__repo_data is None:
            self.gen_repo_data(force=True)

        return self.__repo_data

    def write_mem(self):
        self.writeFile(self.mem_file)
        self.__written = True

    def export_file(self, filename):
        if not self.__written:
            self.write_mem()

        with open(filename, 'w') as f:
            self.mem_file.seek(0)
            shutil.copyfileobj(self.mem_file, f)

    def generate_midi(self, callback=None):
        if self.__verbose:
            print("Creating MIDI…")

        track = 0
        time = 0
        log_channel = 0
        decor_channel = 1

        # Duration of one note
        duration = 0.3

        log_length = len(self.git_log)
        current = 0

        # WRITE THE SEQUENCE
        for section in self.git_log:
            current += 1
            section_len = len(section['file_notes']) * duration

            if callback is not None:
                callback(max_count=log_length, current=current)

            # Add a long note
            if self.__need_commits:
                self.addNote(track, log_channel,
                                  section['commit_note'], time,
                                  section_len, section['commit_volume'])

            if self.__need_files:
                for i, file_note in enumerate(section['file_notes']):
                    self.addNote(track, decor_channel,
                                      file_note['note'], time + i * duration,
                                      duration, file_note['volume'])

            time += section_len

    def __init_pygame(self):
        if self.__pygame_inited:
            return

        # Import pygame stuff here
        import pygame
        import pygame.mixer

        self.pygame = pygame
        self.mixer = pygame.mixer

        # PLAYBACK
        pygame.init()
        pygame.mixer.init()

    def play(self, track=False):
        if self.__verbose:
            print("Playing!")

        self.__init_pygame()

        self.mem_file.seek(0)
        self.mixer.music.load(self.mem_file)
        self.mixer.music.play()
        self.__playing = True

        if not track:
            while self.mixer.music.get_busy():
                sleep(1)

            self.__playing = False

    def stop(self):
        self.mixer.music.stop()

    def get_play_pos(self):
        if not self.__playing:
            return None

        if self.mixer.music.get_busy():
            return self.mixer.music.get_pos()
        else:
            self.__playing = False

            return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Voice of a Repo',
                                     epilog='Use the special value list for ' +
                                     'scale and program to list the ' +
                                     'available program combinations')

    parser.add_argument('repository', type=str, nargs='?', default='.')
    parser.add_argument('--branch',
                        type=str,
                        default='master',
                        help="The branch to generate sound for [master]")
    parser.add_argument('--file',
                        type=str,
                        default=None,
                        help="Save the generated MIDI sequence to this file")
    parser.add_argument('--play',
                        action='store_true',
                        default=False,
                        help="Play the generated file (requires pygame with " +
                        "MIDI support)")
    parser.add_argument('--verbose',
                        action='store_true',
                        default=False,
                        help="Print messages during execution")
    parser.add_argument('--scale',
                        type=str,
                        default=None,
                        help="Scale to use in the generated track")
    parser.add_argument('--program',
                        type=str,
                        default=None,
                        help="Program setting to use in the generated track")
    parser.add_argument('--volume-range',
                        type=int,
                        default=100,
                        help="The volume range to use.")
    parser.add_argument('--skip',
                        type=int,
                        default=0,
                        metavar='N',
                        help="Skip the first N commits " +
                        "(comes in handy if the repo started " +
                        "with some huge commits)")

    args = parser.parse_args()

    if args.scale is None and args.program is None:
        start_gui()

    if args.scale is None and args.program != 'list':
        print("Please specify a scale!")

        sys.exit(1)

    if args.program is None and args.scale != 'list':
        print("Please specify a program!")

        sys.exit(1)

    if args.scale == 'list':
        for scale in scales.keys():
            print(scale)

        sys.exit(0)

    if args.program == 'list':
        for program in programs.keys():
            print(program)

        sys.exit(0)

    if args.scale not in scales:
        print("{} is an unknown scale.".format(args.scale))
        print("Use 'list' to list the available scales.")

        sys.exit(1)

    if args.program not in programs:
        print("{} is an unknown program.".format(args.program))
        print("Use 'list' to list the available programs.")

        sys.exit(1)

    try:
        repo_midi = GitMIDI(repository=args.repository,
                            branch=args.branch,
                            verbose=args.verbose,
                            scale=scales[args.scale][1],
                            program=programs[args.program],
                            volume_range=args.volume_range,
                            skip=args.skip)

    except InvalidGitRepositoryError:
        print("{} is not a valid Git repository" \
              .format(os.path.abspath(args.repository)))

        sys.exit(1)

    except IndexError:
        print("Branch '{}' does not exist in this repo".format(args.branch))

        sys.exit(1)

    repo_midi.gen_repo_data()
    repo_midi.generate_midi()
    repo_midi.write_mem()

    if args.file:
        if args.verbose:
            print("Saving file to {}".format(args.file))

        repo_midi.export_file(args.file)

    if args.play:
        repo_midi.play()
