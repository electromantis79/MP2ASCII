# !/usr/bin/env python
#  -*- coding: utf-8 -*-

"""

.. topic:: Overview

	This module simulates a console with limited functionality of interpreting MP data.

	:Created Date: 3/11/2015
	:Author: **Craig Gunter**

"""

import threading
import time

import app.utils.functions
import app.utils.reads
import app.mp_data_handler
import app.serial_IO.serial_packet
import app.address_mapping

from sys import platform as _platform


class Console(object):
	"""
	Builds a console object.
		*Contains verbose comments option*
	"""

	def __init__(
			self, vbose_list=(1, 0, 0), check_events_flag=True,
			serial_input_flag=0, serial_input_type='MP', serial_output_flag=1, encode_packet_flag=False,
			server_thread_flag=True):
		self.className = 'console'

		self.checkEventsFlag = check_events_flag
		self.serialInputFlag = serial_input_flag
		self.serialInputType = serial_input_type
		self.serialOutputFlag = serial_output_flag
		self.encodePacketFlag = encode_packet_flag
		self.serverThreadFlag = server_thread_flag
		self.vboseList = vbose_list
		self.verbose = self.vboseList[0]  # Method Name or arguments
		self.verboseMore = self.vboseList[1]  # Deeper loop information in methods
		self.verboseMost = self.vboseList[2]  # Crazy Deep Stuff

		app.utils.functions.verbose(['\nCreating Console object'], self.verbose)

		self.MP_StreamRefreshFlag = True
		self.printTimesFlag = False
		self.checkEventsActiveFlag = False
		self.checkEventsOverPeriodFlag = False
		self.ETNSendListCount = 0
		self.ETNSendListLength = 0
		self.verboseDiagnostic = False
		self.print_input_time_flag = False
		self.initTime = time.time()

		self.reset()

	# INIT Functions

	def reset(self, internal_reset=0):
		"""Resets the console to a new game."""
		app.utils.functions.verbose(['\nConsole Reset'], self.verbose)

		# Create Game object
		self.configDict = app.utils.reads.read_config()
		if internal_reset:
			self.game.kill_clock_threads()
		self.game = app.utils.functions.select_sport_instance(self.configDict, number_of_teams=2)

		print 'sport', self.game.gameData['sport'], 'sportType', self.game.gameData['sportType']
		if self.serialInputFlag and self.serialInputType == 'ASCII':
			pass
			# self.game.activeGuestPlayerList = [1,2,3,4,5,6]
			# self.game.activeHomePlayerList = [1,2,3,4,5,6]

		# Build address maps
		self.addrMap = app.address_mapping.AddressMapping(game=self.game)
		self.lampTest = app.address_mapping.LamptestMapping(game=self.game)
		self.blankTest = app.address_mapping.BlanktestMapping(game=self.game)
		self.mp = app.mp_data_handler.MpDataHandler()
		self.addrMap.map()

		# Variables
		self.dirtyDict = {}
		self.sendList = []
		self.ETNSendList = []
		self.ETNStringList = []
		self.quickKeysPressedList = []
		self.sendListFlag = False
		self.ETN_DataFlag = False
		self.ETNSendListFlag = False
		self.quantumTunnelFlag = False
		self.switchKeypadFlag = False
		self.elapseTimeFlag = False
		self.busyCheckEventsFlag = True
		self.keyPressedFlag = False
		
		self.broadcastFlag = False
		self.broadcastString = ''
		self.showOutputString = False
		self.sp = app.serial_IO.serial_packet.SerialPacket(self.game)
		self.serialInputRefreshFrequency = 0.005
		self.serialOutputRefreshFrequency = .1
		self.checkEventsRefreshFrequency = self.game.gameSettings['periodClockResolution']
		self.serialString = ''

		self.MPWordDict = dict(self.addrMap.wordsDict)
		self.previousMPWordDict = dict(self.addrMap.wordsDict)
		self.dataUpdateIndex = 1
		self.shotClockSportsFlag = (
				self.game.gameData['sport'] == 'MPBASKETBALL1' or self.game.gameData['sport'] == 'MPHOCKEY_LX1'
				or self.game.gameData['sport'] == 'MPHOCKEY1')

		self.priorityListEmech = self._select_mp_data_priority()

		self._setup_threads(internal_reset)

	def _select_mp_data_priority(self):
		# Select priority order list
		# G1		B1 = 1,2,3,4		B2 = 5,6,7,8 		B3 = 9,10,11,12, 		B4 = 13,14,15,16
		# G2		B1 = 17,18,19,20 	B2 = 21,22,23,24 	B3 = 25,26,27,28 		B4 = 29,30,31,32
		if self.game.gameData['sportType'] == 'soccer' or self.game.gameData['sportType'] == 'hockey':
			key = 'Sockey'
		elif self.game.gameData['sportType'] == 'stat':
			key = 'Stat'
		else:
			key = '402'
		print 'Priority Key = ', key
		# Add code here for getting to the other priorities

		# All known priorities
		if (
				key == '402'
				and self.game.gameData['sport'] == 'MPFOOTBALL1'
				and self.game.gameSettings['trackClockEnable']

				or key == 'Emech'
		):
			priority_list_emech = [
				18, 11, 22, 1, 6, 5, 21, 2, 7, 25, 9, 8, 24, 3, 23, 4, 20, 19, 17, 12, 10, 16, 15,
				14, 13, 28, 27, 26, 32, 31, 30, 29]
		elif key == '402':
			priority_list_emech = [
				22, 1, 6, 5, 21, 2, 7, 25, 9, 8, 24, 3, 23, 4, 20, 19, 17, 12, 10, 16, 15, 14, 13,
				28, 27, 26, 32, 31, 30, 29, 18, 11]
		elif key == 'Sockey' and self.game.gameData['sportType'] == 'soccer' and self.game.gameSettings[
			'trackClockEnable']:
			priority_list_emech = [
				18, 11, 6, 5, 25, 22, 1, 7, 21, 2, 10, 14, 12, 13, 17, 29, 4, 9, 8, 3, 15, 16, 26,
				30, 24, 20, 23, 19, 28, 27, 32, 31]
		elif key == 'Sockey':
			priority_list_emech = [
				22, 6, 1, 5, 25, 21, 7, 2, 10, 14, 12, 13, 17, 29, 4, 9, 8, 3, 11, 15, 16, 18, 26,
				30, 24, 20, 23, 19, 28, 27, 32, 31]
		elif key == '314' or key == '313':
			priority_list_emech = [
				24, 23, 22, 21, 4, 3, 2, 1, 8, 7, 6, 5, 20, 19, 18, 17, 12, 11, 10, 9, 16, 15, 14,
				13, 28, 27, 26, 25, 32, 21, 30, 29]
		elif key == 'Stat':
			priority_list_emech = self.addrMap.wordListAddrStat
		# self.priority_list_emech = [1,2,3,5,6,7,9,10,11,13,14,15,17,18,19,21,22,
		# 23,33,34,35,37,38,39,41,42,43,45,46,47,49,50,51,53,54,55]
		else:
			priority_list_emech = range(32)
		return priority_list_emech

	def _setup_threads(self, internal_reset):
		# Platform Dependencies
		if _platform == "linux" or _platform == "linux2":
			print 'Platform is', _platform
			if self.serialInputFlag and not internal_reset:
				app.utils.functions.verbose(['\nSerial Input On'], self.verbose)
				import serial_IO.mp_serial
				self.s = serial_IO.mp_serial.MpSerialHandler(serial_input_type=self.serialInputType, game=self.game)
				self.refresherSerialInput = threading.Thread(
					target=app.utils.functions.thread_timer, args=(self._serial_input, self.serialInputRefreshFrequency))
				self.refresherSerialInput.daemon = True
				self.refresherSerialInput.name = '_serial_input'
				self.alignTime = 0.0
				self.previousByteCount = 0
				self.refresherSerialInput.start()

				# Must happen this at least fast for tenth of a second to fully update
				# because it could land before or after the change
				self.checkEventsRefreshFrequency = self.checkEventsRefreshFrequency/2

			if self.checkEventsFlag and not internal_reset:
				self.refresherCheckEvents = threading.Thread(
					target=app.utils.functions.thread_timer, args=(self._check_events, self.checkEventsRefreshFrequency))
				self.refresherCheckEvents.daemon = True
				self.refresherCheckEvents.name = '_check_events'
				self.refresherCheckEvents.start()

			if self.serialOutputFlag and not internal_reset:
				app.utils.functions.verbose(['\nSerial Output On'], self.verbose)
				
				# Wait till we have an alignTime stamped from _check_events
				time.sleep(0.1)
				
				self.refresherSerialOutput = threading.Thread(
					target=app.utils.functions.thread_timer,
					args=(self._serial_output, self.serialOutputRefreshFrequency, None, self.alignTime))
				self.refresherSerialOutput.daemon = True
				self.refresherSerialOutput.name = '_serial_output'
				self.refresherSerialOutput.start()		

		elif _platform == "darwin":
			#  OS X
			print 'Apple Sucks!!!!!', 'Disabling input and output flags'
			self.serialOutputFlag = False
			self.serialInputFlag = False
		elif _platform == "win32":
			print '\nSerial Input not working for', _platform, 'Disabling input and output flags'
			self.serialOutputFlag = False
			self.serialInputFlag = False
			# self.showOutputString = True
			if self.checkEventsFlag and not internal_reset:
				threading.Timer(.1, self._check_events).start()
				
			if self.serialOutputFlag and not internal_reset:
				app.utils.functions.verbose(['\nSerial Output On'], self.verbose)
				self.refresherSerialOutput = threading.Thread(
					target=app.utils.functions.thread_timer, args=(self._serial_output, self.serialOutputRefreshFrequency))
				self.refresherSerialOutput.daemon = True
				self.refresherSerialOutput.name = '_serial_output'
				self.refresherSerialOutput.start()

	# THREADS

	def _serial_input(self):
		"""Inputs serial packets."""
		if self.print_input_time_flag:
			tic = time.time()
			init_elapse = tic-self.initTime
			print '(serial Input %s)' % init_elapse

		self.s.serial_input()

	def _serial_output(self):
		"""Outputs serial packets."""
		if self.printTimesFlag or self.verboseDiagnostic:
			tic = time.time()
			init_elapse = tic-self.initTime
			print '(-----------serial Output %s)' % init_elapse

		try:
			if self.ETNStringList:
				string = self.ETNStringList[-1]
				self.ETNStringList.pop(0)
				if 1 or self.verboseDiagnostic:
					print 'Serial Output', string, 'len(self.ETNStringList)', len(self.ETNStringList)
			else:
				string = self.serialString

			self.s.serial_output(string)
			if self.verboseDiagnostic:
				print 'Serial Output', self.serialString
		except:
			if not (_platform == "win32" or _platform == "darwin"):
				print 'Serial Output Error', self.serialString

	# Timer called events for the main program -----------------

	def _check_events(self):
		"""
		Checks all events.

		This is called at the checkEventsRefreshFrequency and could be thought of as the main interrupt in a micro-controller.

		The console only updates data for the outside world at this time.
		"""
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

			self.addrMap.un_map(self.s.receiveList)

			# This aligns the output to after the input receive gap starts (This only effects the start of output thread)
			if not self.previousByteCount:
				# This should make the output thread fire shift_time ms before the next check events firing
				shift_time = 0.001
				self.alignTime = tic + self.checkEventsRefreshFrequency - shift_time

			# Clear receive list
			self.previousByteCount = len(self.s.receiveList)
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
				self.checkEventsOverPeriodFlag = True

			self.checkEventsActiveFlag = False


def test():
	"""Creates an interpreter."""
	print "ON"
	sport = 'MPBASKETBALL1'
	c = Config()
	c.write_sport(sport)
	c.write_option_jumpers('0000')
	Console(
		check_events_flag=True, serial_input_flag=True, serial_input_type='MP',
		serial_output_flag=True, encode_packet_flag=True, server_thread_flag=True)
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
