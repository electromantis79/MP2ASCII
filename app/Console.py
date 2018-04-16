# !/usr/bin/env python
#  -*- coding: utf-8 -*-

"""

.. topic:: Overview

	This module simulates a console with the limited functionality of converting MP data to an ASCII packet.

	:Created Date: 3/11/2015
	:Author: **Craig Gunter**

"""

import threading
import time

import app.utils.functions
import app.utils.reads
import app.address_mapping
import app.serial_IO.serial_packet

from sys import platform as _platform


class Console(object):
	"""
	Builds a console object only geared to convert MP data to ASCII data.
	"""

	def __init__(
			self, check_events_flag=True, serial_input_flag=False, serial_input_type='MP',
			serial_output_flag=True, encode_packet_flag=False,	server_thread_flag=False):
		self.initTime = time.time()

		self.checkEventsFlag = check_events_flag
		self.serialInputFlag = serial_input_flag
		self.serialInputType = serial_input_type
		self.serialOutputFlag = serial_output_flag
		self.encodePacketFlag = encode_packet_flag
		self.serverThreadFlag = server_thread_flag

		# Print Flags
		self.printProductionInfo = True
		self.printTimesFlag = False
		self.printInputTimeFlag = False
		self.ETNPrintOutputFlag = False
		self.verboseDiagnostic = False

		app.utils.functions.verbose(['\nCreating Console object'], self.printProductionInfo)

		# Thread times in seconds
		self.serialInputRefreshFrequency = 0.005
		self.serialOutputRefreshFrequency = 0.1
		self.checkEventsRefreshFrequency = 0.1

		# Variables that don't need resetting through internal reset
		self.className = 'console'
		self.serialString = ''
		self.ETNStringList = []
		self.checkEventsActiveFlag = False
		self.switchKeypadFlag = False

		# Main module items set in reset
		self.configDict = None
		self.game = None
		self.addrMap = None
		self.sp = None

		self.reset()

	# INIT Functions

	def reset(self, internal_reset=0):
		"""Resets the console to a new game."""
		app.utils.functions.verbose(['\nConsole Reset'], self.printProductionInfo)

		# Create Game object
		self.configDict = app.utils.reads.read_config()
		if internal_reset:
			self.game.kill_clock_threads()
		self.game = app.utils.functions.select_sport_instance(self.configDict, number_of_teams=2)

		app.utils.functions.verbose(
			['sport', self.game.gameData['sport'], 'sportType', self.game.gameData['sportType']],
			self.printProductionInfo)

		self.addrMap = app.address_mapping.AddressMapping(game=self.game)

		self.sp = app.serial_IO.serial_packet.SerialPacket(self.game)

		self._setup_threads(internal_reset)

	def _setup_threads(self, internal_reset):
		# Platform Dependencies
		if _platform == "linux" or _platform == "linux2":
			print 'Platform is', _platform
			if self.serialInputFlag and not internal_reset:
				app.utils.functions.verbose(['\nSerial Input On'], self.printProductionInfo)

				import serial_IO.mp_serial

				self.s = serial_IO.mp_serial.MpSerialHandler(serial_input_type=self.serialInputType, game=self.game)
				self.refresherSerialInput = threading.Thread(
					target=app.utils.functions.thread_timer, args=(self._serial_input, self.serialInputRefreshFrequency))
				self.refresherSerialInput.daemon = True
				self.refresherSerialInput.name = '_serial_input'
				self.alignTime = 0.0
				self.previousByteCount = 0
				self.refresherSerialInput.start()

				# Must happen at least this fast for tenth of a second to fully update
				# because it could land before or after the change
				self.checkEventsRefreshFrequency = self.checkEventsRefreshFrequency/2

			if self.checkEventsFlag and not internal_reset:
				self.refresherCheckEvents = threading.Thread(
					target=app.utils.functions.thread_timer, args=(self._check_events, self.checkEventsRefreshFrequency))
				self.refresherCheckEvents.daemon = True
				self.refresherCheckEvents.name = '_check_events'
				self.refresherCheckEvents.start()

			if self.serialOutputFlag and not internal_reset:
				app.utils.functions.verbose(['\nSerial Output On'], self.printProductionInfo)
				
				# Wait till we have an alignTime stamped from _check_events
				time.sleep(0.1)
				
				self.refresherSerialOutput = threading.Thread(
					target=app.utils.functions.thread_timer,
					args=(self._serial_output, self.serialOutputRefreshFrequency, None, self.alignTime))
				self.refresherSerialOutput.daemon = True
				self.refresherSerialOutput.name = '_serial_output'
				self.refresherSerialOutput.start()

	# THREADS

	def _serial_input(self):
		if self.printInputTimeFlag:
			tic = time.time()
			init_elapse = tic-self.initTime
			print '(serial Input %s)' % init_elapse

		self.s.serial_input()

	def _serial_output(self):
		if self.printTimesFlag or self.verboseDiagnostic:
			tic = time.time()
			init_elapse = tic-self.initTime
			print '(-----------serial Output %s)' % init_elapse

		try:
			if self.ETNStringList:
				string = self.ETNStringList[-1]
				self.ETNStringList.pop(0)
				if self.ETNPrintOutputFlag or self.verboseDiagnostic:
					print 'Serial Output', string, 'len(self.ETNStringList)', len(self.ETNStringList)
			else:
				string = self.serialString

			self.s.serial_output(string)
			if self.verboseDiagnostic:
				print 'Serial Output', self.serialString
		except:
			if not (_platform == "win32" or _platform == "darwin"):
				print 'Serial Output Error', self.serialString

	def _check_events(self):
		tic = time.time()
		if self.printTimesFlag or self.verboseDiagnostic:
			init_elapse = tic-self.initTime
			print '(-----_check_events %s)' % init_elapse

		# This is how the check events function is called when not on linux
		if (_platform == "win32" or _platform == "darwin") and self.checkEventsFlag:
			self.checkEventsTimer = threading.Timer(self.checkEventsRefreshFrequency, self._check_events).start()

		# This flag is to eliminate double entry to this area
		if not self.checkEventsActiveFlag:
			self.checkEventsActiveFlag = True

			# This aligns the output to after the input receive gap starts (This only effects the start of output thread)
			if not self.previousByteCount:
				# This should make the output thread fire shift_time ms before the next check events firing
				shift_time = 0.001
				self.alignTime = tic + self.checkEventsRefreshFrequency - shift_time
			self.previousByteCount = len(self.s.receiveList)

			# Save any good data received to the game
			self.addrMap.un_map(self.s.receiveList)
			self.s.receiveList = []

			# Reset sport
			if self.addrMap.game.gameSettings['resetGameFlag']:
				print 'internal_reset triggered'
				time.sleep(.05)
				self.reset(internal_reset=1)
				self.switchKeypadFlag = True

			# Build output string or ETN string list
			if self.addrMap.quantumETNTunnelNameProcessed:
				self.addrMap.quantumETNTunnelNameProcessed = False

				serial_string = self.sp.process_packet(print_string=False, e_t_n_flag=True, packet=None)
				self.ETNStringList.append(serial_string)

				# Because we are running check_events twice per output sometimes a one-shot ETN packet can get missed
				# This redundant doubling of the string buffer ensures it is not lost
				self.ETNStringList.append(serial_string)

			elif self.addrMap.quantumETNTunnelFontJustifyProcessed:
				self.addrMap.quantumETNTunnelFontJustifyProcessed = False

				serial_string = self.sp.process_packet(print_string=False, e_t_n_flag=True, packet=None)
				if self.serialString != serial_string:
					self.ETNStringList.append(serial_string)

			else:
				self.serialString = self.sp.process_packet(print_string=False, e_t_n_flag=False, packet=None)

			# Time measurement for testing
			toc = time.time()
			elapse = (toc-tic)
			if elapse > self.checkEventsRefreshFrequency:  # For testing only
				print '_check_events elapse', elapse*1000, ' ms'
				print

			self.checkEventsActiveFlag = False


def test():
	"""Runs the converter with the sport and jumper settings hardcoded in this function."""
	print "ON"
	sport = 'MPSOCCER_LX1-soccer'
	jumpers = 'B000'
	print 'sport', sport, 'jumpers', jumpers

	c = Config()
	c.write_sport(sport)
	c.write_option_jumpers(jumpers)

	Console(
		check_events_flag=True, serial_input_flag=True, serial_input_type='MP',
		serial_output_flag=True, encode_packet_flag=True, server_thread_flag=False)
	while 1:
		time.sleep(2)
		# break

	# SPORT_LIST = [
	# 'MMBASEBALL3', 'MPBASEBALL1', 'MMBASEBALL4', 'MPLINESCORE4', 'MPLINESCORE5',
	# 'MPMP-15X1', 'MPMP-14X1', 'MPMULTISPORT1-baseball', 'MPMULTISPORT1-football', 'MPFOOTBALL1', 'MMFOOTBALL4',
	# 'MPBASKETBALL1', 'MPSOCCER_LX1-soccer', 'MPSOCCER_LX1-football', 'MPSOCCER1', 'MPHOCKEY_LX1', 'MPHOCKEY1',
	# 'MPCRICKET1', 'MPRACETRACK1', 'MPLX3450-baseball', 'MPLX3450-football', 'MPGENERIC',  'MPSTAT']


if __name__ == '__main__':
	from config_default_settings import Config
	test()
