# -*- coding: utf-8
"""
The GitMIDI class that converts a Git repository’s log into MIDI music.
"""

from __future__ import print_function

import os
import shutil

from midiutil.MidiFile import MIDIFile
from StringIO import StringIO
from git import Repo, Tree
from git.objects.blob import Blob
from time import sleep

try:
    import pygame
    import pygame.mixer
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


def get_file_sha(commit, file_name):
    """
    Get the SHA1 ID of a file by its name, in the given commit.
    """

    elements = file_name.split(os.sep)
    tree = commit.tree

    while True:
        try:
            element = elements.pop(0)

            if isinstance(tree[element], Tree):
                tree = tree[element]
        except (KeyError, IndexError):
            # The file has been deleted, return the hash of an empty file
            return 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'

        if isinstance(tree, Blob):
            break

    return tree.hexsha


class GitMIDI(MIDIFile):
    """
    Class to hold repository data, and MIDI data based on that repository.
    """

    LOG_CHANNEL = 0
    FILE_CHANNEL = 1

    def __setup_midi(self, track_title=None):
        """
        Initialise the MIDI file.
        """

        if self.__verbose:
            print("Preparing MIDI track…")

        if track_title is None:
            # TODO: Change this to something that connects to the repo
            self.addTrackName(0, 0, "Sample Track")

            self.addTempo(0, 0, self.__tempo)

            if self.__need_commits:
                self.addProgramChange(0, self.LOG_CHANNEL,
                                      0, self.__program['commit']['program'])

            if self.__need_files:
                self.addProgramChange(0, self.FILE_CHANNEL,
                                      0, self.__program['file']['program'])

    def __setup_repo(self):
        """
        Setup repository and get the specified branch.
        """

        if self.__verbose:
            print("Analyzing repository…")

        repo = Repo(self.__repo_dir)
        self.__branch_head = repo.heads[self.__branch].commit

    def __init__(self,
                 repository=None,
                 branch=None,
                 verbose=None,
                 scale=None,
                 program=None,
                 volume_range=None,
                 skip=None,
                 note_duration=None,
                 max_beat_len=None,
                 tempo=None):
        MIDIFile.__init__(self, 1)

        self.__verbose = verbose or False
        self.__written = False
        self.__repo_dir = repository or '.'
        self.__repo = None
        self.__branch = branch or 'master'
        self.__branch_head = None
        self.__repo_data = None
        self.__git_log = []
        self.__mem_file = StringIO()
        self.__scale = scale
        self.__program = program
        self.__volume_deviation = min(abs(63 - (volume_range or 107)), 63)
        self.__pygame_inited = False
        self.__playing = False
        self.__skip = skip or 0
        self.__note_duration = note_duration or 0.3
        self.__max_beat_len = max_beat_len
        self.__tempo = tempo or 120

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
        """
        Calculate note based on an SHA1 hash
        """

        note_num = reduce(lambda res, digit: res + int(digit, 16),
                          list(str(sha)), 0) % len(self.__scale)

        return self.__scale[note_num]

    def gen_beat(self, commit):
        """
        Generate data for a beat based on a commit and its files.
        """

        stat = commit.stats

        file_notes = []
        file_count = 0

        for file_name, file_stat in stat.files.items():
            file_count += 1

            if self.__max_beat_len is not None and \
               self.__max_beat_len != 0 and \
               file_count > self.__max_beat_len:
                break

            volume_mod = self.__program['file'].get('volume', 0)
            file_note = self.sha_to_note(get_file_sha(commit, file_name)) + \
                        self.__program['file']['octave'] * 12
            file_volume = self.gen_volume(file_stat['deletions'],
                                          file_stat['insertions'],
                                          volume_mod)

            file_notes.append({
                'note': file_note,
                'volume': file_volume,
            })

        volume_mod = self.__program['commit'].get('volume', 0)

        commit_note = self.sha_to_note(commit.hexsha) + \
                      self.__program['commit']['octave'] * 12
        commit_volume = self.gen_volume(stat.total['deletions'],
                                        stat.total['insertions'],
                                        volume_mod)

        return {
            'commit_note': commit_note,
            'commit_volume': commit_volume,
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
        to_process = [self.__branch_head]

        while len(to_process) > 0:
            counter += 1

            # TODO: Make this 500 configurable
            if counter % 500 == 0 and self.__verbose:
                print("Done with {} commits".format(counter))

            current_commit = to_process.pop()

            if callback is not None:
                callback(None, None)

            if current_commit not in self.__repo_data:
                self.__repo_data.append(current_commit)
                to_process += current_commit.parents

        if self.__verbose:
            print("{} commits found".format(counter))
            print("Sorting commits…")

        self.__repo_data.sort(key=lambda commit: commit.authored_date)

        if self.__verbose:
            print("Generating MIDI data…")

        self.__git_log = []
        current_commit = 0
        commits_to_process = self.__repo_data[self.__skip:]
        commit_count = len(commits_to_process)

        for commit in commits_to_process:
            if callback:
                current_commit += 1
                callback(commit_count, current_commit)

            self.__git_log.append(self.gen_beat(commit))

    @property
    def repo_data(self):
        """
        Get repository data for MIDI generation.
        """

        if self.__repo_data is None:
            self.gen_repo_data(force=True)

        return self.__repo_data

    def write_mem(self):
        """
        Write MIDI data to the memory file.
        """

        self.writeFile(self.__mem_file)
        self.__written = True

    def export_file(self, filename):
        """
        Export MIDI data to a file.
        """

        if not self.__written:
            self.write_mem()

        with open(filename, 'w') as midi_file:
            self.__mem_file.seek(0)
            shutil.copyfileobj(self.__mem_file, midi_file)

    def generate_midi(self, callback=None):
        """
        Generate MIDI data.
        """

        if self.__verbose:
            print("Creating MIDI…")

        track = 0
        time = 0
        log_channel = 0
        decor_channel = 1

        log_length = len(self.__git_log)
        current = 0

        # WRITE THE SEQUENCE
        for section in self.__git_log:
            current += 1
            section_len = len(section['file_notes']) * self.__note_duration

            if callback is not None:
                callback(log_length, current)

            # Add a long note
            if self.__need_commits:
                self.addNote(track, log_channel,
                             section['commit_note'], time,
                             section_len, section['commit_volume'])

            if self.__need_files:
                for i, file_note in enumerate(section['file_notes']):
                    self.addNote(track, decor_channel,
                                 file_note['note'],
                                 time + i * self.__note_duration,
                                 self.__note_duration, file_note['volume'])

            time += section_len

    def __init_pygame(self):
        """
        Initialise pygame.
        """

        if not PYGAME_AVAILABLE or self.__pygame_inited:
            return

        # Initialise pygame
        pygame.init()
        pygame.mixer.init()

    def play(self, track=False):
        """
        Start MIDI playback. If pygame is not available, don’t do anything.
        """

        if not PYGAME_AVAILABLE:
            return "pygame is not available, cannot start playback"

        if self.__verbose:
            print("Playing!")

        self.__init_pygame()

        self.__mem_file.seek(0)
        pygame.mixer.music.load(self.__mem_file)
        pygame.mixer.music.play()
        self.__playing = True

        if not track:
            while pygame.mixer.music.get_busy():
                sleep(1)

            self.__playing = False

    def stop(self):
        """
        Stop MIDI playback.
        """

        if not PYGAME_AVAILABLE:
            return

        pygame.mixer.music.stop()

    def get_play_pos(self):
        """
        Get current playback position from the mixer
        """

        if not self.__playing:
            return None

        if pygame.mixer.music.get_busy():
            return pygame.mixer.music.get_pos()
        else:
            self.__playing = False

            return None
