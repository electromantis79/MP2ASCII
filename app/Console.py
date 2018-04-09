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
				if self.serialInputType == 'ASCII':
					self.serialInputRefreshFrequency = .1
				self.refresherSerialInput = threading.Thread(
					target=app.utils.functions.thread_timer, args=(self._serial_input, self.serialInputRefreshFrequency))
				self.refresherSerialInput.daemon = True
				self.refresherSerialInput.name = '_serial_input'
				self.alignTime = 0.0
				self.previousByteCount = 0
				self.refresherSerialInput.start()
				if self.serialInputType == 'MP':
					self.checkEventsRefreshFrequency = self.checkEventsRefreshFrequency/2

			if self.checkEventsFlag and not internal_reset:
				if self.serialInputType == 'ASCII':
					pass  # time.sleep(0.2) #  This delay seems to cause packet corruption
				self.refresherCheckEvents = threading.Thread(
					target=app.utils.functions.thread_timer, args=(self._check_events, self.checkEventsRefreshFrequency))
				self.refresherCheckEvents.daemon = True
				self.refresherCheckEvents.name = '_check_events'
				self.refresherCheckEvents.start()

			if self.serialOutputFlag and not internal_reset:
				app.utils.functions.verbose(['\nSerial Output On, self.encodePacketFlag', self.encodePacketFlag], self.verbose)
				
				# Wait till we have an alignTime stamped from _check_events
				if self.serialInputType == 'MP':
					time.sleep(0.3)
				else:
					time.sleep(0.05)
				
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
				app.utils.functions.verbose(['\nSerial Output On, self.encodePacketFlag', self.encodePacketFlag], self.verbose)
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
			self.s.serial_output(self.serialString)
			if self.printTimesFlag or self.verboseDiagnostic or self.ETNSendListFlag:
				pass  # print 'Serial Output', self.serialString
		except:
			if not (_platform == "win32" or _platform == "darwin"):
				print 'Serial Output Error', self.serialString

	# Timer called events for the main program -----------------

	def _check_events(self):
		"""
		Checks all events.

		This is called at the checkEventsRefreshFrequency and could be thought of as the main interrupt in a microcontroller.

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
			
			if self.serialInputFlag:
				# Area for externally generated game data
				if self.serialInputType == 'ASCII':
					if self.s.ETNpacketList and not self.ETNSendListFlag:
						packet = self.s.ETNpacketList[-1]
						self.s.ETNpacketList.pop(0)
					else:
						packet = self.s.packet
					self.sp.encode_packet(print_string=False, packet=packet)
				elif self.serialInputType == 'MP':
					# This area is called 10X faster than normal else area
					
					self.addrMap.un_map(self.s.receiveList)
					
					# This aligns the output to after the input receive gap starts
					if self.previousByteCount and len(self.s.receiveList) == 0:
						# This should make the output thread fire shift_time ms before the next check events firing
						shift_time = 0.001
						self.alignTime = tic + self.checkEventsRefreshFrequency - shift_time
					self.previousByteCount = len(self.s.receiveList)

					# Clear buffered MP words
					self.s.receiveList = []

					# Reset sport
					if (
							self.game.gameSettings['resetGameFlag']
							or self.addrMap.game.gameSettings['resetGameFlag']
							or not self.game.gameSettings['restoreGameFlag']
					):
						time.sleep(.05)
						self.reset(internal_reset=1)
						self.switchKeypadFlag = True

			if not self.serialInputFlag or self.serialInputType == 'ASCII':
				# Area for internally generated game data
				# Handle all events, update MP data, and form sendString

				if self.serialInputType != 'ASCII':
					self.timeEvents()

					self.dataEvents()				
				
				self.updateMPData()

				self.updateMP_Packet()

			if self.encodePacketFlag:
				if self.serialInputType == 'ASCII':
					# ASCII coming in
					pass
				else:
					# MP coming in
					# print 'self.addrMap.quantumETNTunnel', self.addrMap.quantumETNTunnel
					packet = None

					if self.addrMap.quantumETNTunnelProcessed:
						self.addrMap.quantumETNTunnelProcessed = False
						e_t_n_flag = True
						self.serialString = self.sp.encode_packet(
							print_string=True, e_t_n_flag=e_t_n_flag, packet=packet)
					else:
						e_t_n_flag = False

						self.serialString = self.sp.encode_packet(
							print_string=False, e_t_n_flag=e_t_n_flag, packet=packet)

			# Time measurement for testing
			toc = time.time()
			elapse = (toc-tic)
			if elapse > self.checkEventsRefreshFrequency:  # For testing only
			
				print '_check_events elapse', elapse*1000, ' ms'
				print
				self.checkEventsOverPeriodFlag = True
			self.checkEventsActiveFlag = False
			
		# End Check Events --------------------------------------------------------------------

	def timeEvents(self):
		"""Checks time related events."""
		vboseList = self._vboseLCDSave()
		self.lcd.RefreshScreen(self.game)
		self._vboseLCDLoad(vboseList)

		# Start menu timer
		if self.lcd.menuTimerFlag and not self.lcd.currentMenuString == 'yardsToGoReset':
			self.lcd.menuTimerFlag = False
			self.cancelMenuTimer()
			duration = self.game.gameSettings['menuTimerDuration']
			if self.lcd.currentMenuString == 'NewGame' and self.game.configDict['keypadType'] == 'MM':
				duration = 2
			self.menuTimer = threading.Timer(duration, self.defaultScreen)
			self.menuTimer.start()

		# Stop menu timer
		if self.game.gameSettings['blankTestFlag'] or self.game.gameSettings['lampTestFlag'] or self.lcd.currentMenuString == 'segmentTimerMenu' or self.game.gameSettings['resetGameFlag']:
			self.cancelMenuTimer()

		# Colon Decimal
		if not self.serialInputFlag:
			self.colonDecimal()

		# Horn section
		if self.game.clockDict['periodClock'].autoStop:
			self.game.clockDict['periodClock'].autoStop = False
			self.game.Horn()
			self.broadcastString += 'P0'
			self.broadcastFlag = True
		if self.shotClockSportsFlag and self.game.clockDict['shotClock'].autoStop:
			self.game.clockDict['shotClock'].autoStop = False
			self.game.shotHorn()
		if not self.game.gameData['sportType'] == 'stat':
			if not self.shotClockSportsFlag and self.game.clockDict['delayOfGameClock'].autoStop:
				self.game.clockDict['delayOfGameClock'].autoStop = False
				self.game.delayOfGameHorn()
		if self.game.clockDict['timeOutTimer'].autoStop:
			self.game.gameSettings['timeOutTimerEnable'] = False
			self.game.clockDict['timeOutTimer'].reset_()
			temp = self.game.gameSettings['endOfPeriodHornEnable']
			self.game.gameSettings['endOfPeriodHornEnable'] = False
			self.game.Horn()
			self.game.gameSettings['endOfPeriodHornEnable'] = temp

		# If a shot clock sport and period Clock is on then start the shot Clock
		if (
				self.shotClockSportsFlag
				and self.game.clockDict['periodClock'].running
				and not self.game.clockDict['shotClock'].running
				and self.game.clockDict['shotClock'].timeUnitsDict['currentTime'] > 0
		):
			self.game.clockDict['shotClock'].start_()

		# Start team name number pad timer
		if self.lcd.teamNameNumpadFlag:
			self.lcd.teamNameNumpadFlag = False
			self.lcd.teamNameNumpadTimerFlag = True
			self.ETN_DataFlag = True
			self.quantumTunnelFlag = True
			self.cancelTeamNameNumpadTimer()
			duration = 2
			self.teamNameNumpadTimer = threading.Timer(duration, self.cancelTeamNameNumpadTimerFlag)
			self.teamNameNumpadTimer.start()

		# Start splash screen timer
		if self.lcd.splashTimerFlag:
			self.lcd.splashTimerFlag = False
			threading.Timer(self.game.configDict['splashTime'], self.splashTimerEnded).start()

		# Reset sport
		if (
				self.game.gameSettings['resetGameFlag']
				or self.addrMap.game.gameSettings['resetGameFlag']
				or not self.game.gameSettings['restoreGameFlag']
		):
			self.game.gameSettings['resetGameFlag'] = False
			time.sleep(.05)
			self.reset(internal_reset=1)
			if self.className == 'scoreboard':
				print 'Scoreboard Graphics Reset'
				self.resetGraphicsFlag = True
				# self.boardReset()
			self.switchKeypadFlag = True

	def _vboseLCDSave(self):
		vbose_list = [self.lcd.verbose, self.lcd.verboseMore, self.lcd.verboseMost]
		self.lcd.verbose = 0  # Method Name or arguments
		self.lcd.verboseMore = 0  # Deeper loop information in methods
		self.lcd.verboseMost = 0  # Crazy Deep Stuff
		return vbose_list

	def _vboseLCDLoad(self, vbose_list):
		self.lcd.verbose = vbose_list[0]  # Method Name or arguments
		self.lcd.verboseMore = vbose_list[1]  # Deeper loop information in methods
		self.lcd.verboseMost = vbose_list[2]  # Crazy Deep Stuff

	def colonDecimal(self):
		"""Updates the colon and decimal."""
		if self.game.clockDict['periodClock'].currentTime < 60:
			if self.game.gameSettings['trackClockEnable']:
				if self.game.gameSettings['periodClockTenthsFlag']:
					self.game.gameData['colonIndicator'] = True
					self.game.gameData['decimalIndicator'] = True
				else:
					self.game.gameData['colonIndicator'] = True
					self.game.gameData['decimalIndicator'] = False
			elif self.game.gameData['sportType'] == 'baseball' and not (
					self.game.sport == 'MPMULTISPORT1-baseball' or self.game.sport == 'MPLX3450-baseball'):
				self.game.gameData['colonIndicator'] = True
				self.game.gameData['decimalIndicator'] = False
			else:
				if self.game.gameSettings['periodClockTenthsFlag'] and not self.game.gameSettings['timeOutTimerEnable']:
					self.game.gameData['colonIndicator'] = False
					self.game.gameData['decimalIndicator'] = True
				else:
					self.game.gameData['colonIndicator'] = True
					self.game.gameData['decimalIndicator'] = False
		else:
			if self.game.gameSettings['clock_3D_or_less_Flag'] or self.game.gameSettings['2D_Clock']:
				if self.game.clockDict['periodClock'].timeUnitsDict['tenthsUnits'] < 5:
					self.game.gameData['colonIndicator'] = False
				else:
					self.game.gameData['colonIndicator'] = True
				self.game.gameData['decimalIndicator'] = False
			else:
				if self.game.gameSettings['trackClockEnable']:
					if self.game.gameSettings['periodClockTenthsFlag']:
						self.game.gameData['colonIndicator'] = True
						self.game.gameData['decimalIndicator'] = True
					else:
						self.game.gameData['colonIndicator'] = True
						self.game.gameData['decimalIndicator'] = False
				else:
					self.game.gameData['colonIndicator'] = True
					self.game.gameData['decimalIndicator'] = False

	# Timer triggered menu events ------------------------

	def defaultScreen(self):
		"""Displays the default screen on the LCD."""
		if self.lcd.menuFlag:
			app.utils.functions.verbose(['\nDEFAULT SCREEN'], self.verbose)
			self.lcd.exitMenu(self.game)
		else:
			self.cancelMenuTimer()

	def cancelMenuTimer(self):
		"""Cancels the menu timer."""
		try:
			self.menuTimer.cancel()
		except:
			pass

	def cancelTeamNameNumpadTimer(self):
		"""Cancels the menu timer."""
		try:
			self.teamNameNumpadTimer.cancel()
		except:
			pass

	def cancelTeamNameNumpadTimerFlag(self):
		"""Cancels the team name number pad timer."""
		self.lcd.teamNameNumpadTimerFlag = False

	def splashTimerEnded(self):
		"""Performs events after splash screen."""
		if not self.game.gameSettings['multisportMenuFlag']:
			self.game.gameSettings['resetGameFlag'] = True
		else:
			self.lcd.map(self.game, funcString='Splash')
			self.lcd.menuTimerFlag = True

	# ---------------------------------------------------------------

	def dataEvents(self):
		"""Checks data related events."""
		# If dimming flag then send tunneling bytes
		if self.game.gameSettings['dimmingFlag']:  # each entry cycles through 6 brightness levels and sends them to each bank
			self.game.gameSettings['dimmingFlag'] = False
			# ADD addrMap stuff for tunneling here

		# If timeOfDayClock is off then turn off timeOfDayClockBlanking
		if not self.game.gameSettings['timeOfDayClockEnable']:
			self.game.gameSettings['timeOfDayClockBlankingEnable'] = False

	# ---------------------------------------------------------------

	def updateMPData(self):
		"""Update address map and MPWordDict and send to drivers if class is scoreboard."""
		tic = time.time()
		# print tic

		# Select current map

		if self.game.gameSettings['blankTestFlag']:
			self.blankTest.map()
			self.MPWordDict = dict(self.blankTest.wordsDict)
		elif self.game.gameSettings['lampTestFlag']:
			self.lampTest.map()
			self.MPWordDict = dict(self.lampTest.wordsDict)
		else:
			self.addrMap.map()
			self.MPWordDict = dict(self.addrMap.wordsDict)

		toc = time.time()

		# print 'updateMPData Time  = ',(toc-tic)*1000, ' milliseconds'

	# ---------------------------------------------------------------

	def updateMP_Packet(self):
		"""Updates 18 bytes (9 MP words) into self.sendList."""

		# Check for changes in data
		if cmp(self.MPWordDict, self.previousMPWordDict) != 0:
			for address in self.MPWordDict.keys():
				if self.previousMPWordDict[address] != self.MPWordDict[address]:
					self.dirtyDict[address] = self.MPWordDict[address]
		self.previousMPWordDict = dict(self.MPWordDict)

		# Clear sendList
		self.sendList = []

		# Print dirty list
		if len(self.dirtyDict) and self.verboseDiagnostic:
			print '\n---self.dirtyDict', self.dirtyDict, '\nlength', len(self.dirtyDict)

		# Make custom sendList for menu controlled ETNs
		if self.quantumTunnelFlag:
			self.quantumTunnelFlag = False
			if self.ETN_DataFlag:
				self.ETN_DataFlag = False
				if self.lcd.currentMenuString == 'teamNameMenu':
					if self.lcd.menuNumber == 1 or self.lcd.menuNumber == 4:

						# ETN character change section
						length = len(self.lcd.teamNameString)
						teamAddr = length/2+1

						if self.lcd.menuNumber == 1:
							teamAddrShift = 0
						elif self.lcd.menuNumber == 4:
							teamAddrShift = 64

						if length:
							if length % 2:
								leftETNByte = ord(self.lcd.teamNameString[-1])
								rightETNByte = 0
								teamAddr = length/2+1
							else:
								leftETNByte = ord(self.lcd.teamNameString[-2])
								rightETNByte = ord(self.lcd.teamNameString[-1])
								teamAddr = length/2
						else:
							leftETNByte = ord(' ')
							rightETNByte = 0

						# 0xbc = tunnel code
						# word 2 = address of character pair
						# word 3 = leftETNByte
						# word 4 = rightETNByte or controlByte(if addr = 0or64)
						print (
							'teamAddr', teamAddr, 'teamAddrShift', teamAddrShift,
							'leftETNByte', leftETNByte, 'rightETNByte', rightETNByte)
						word1 = self.mp.encode(2, 4, 1, 0, 1, 10, 13, 0, 0)
						word2 = self.mp.encode(2, 4, 2, 0, 0, 0, teamAddr + teamAddrShift, 0, 0, pass3_4_flag=True)
						word3 = self.mp.encode(2, 4, 3, 0, 0, 0, leftETNByte, 0, '', pass3_4_flag=True)
						word4 = self.mp.encode(2, 4, 4, 0, 0, 0, rightETNByte, 0, '', pass3_4_flag=True)
						# Check data stream insertion
						sendList = [
							word1, word2, word3, word4, self.MPWordDict[29],
							self.MPWordDict[30], self.MPWordDict[31], self.MPWordDict[32]]

					else:

						# ETN Font and Justify section
						teamAddr = 0
						teamG = self.game.guest
						teamH = self.game.home
						if self.lcd.menuNumber == 2 or self.lcd.menuNumber == 3:
							teamAddrShift = 0
						else:
							teamAddrShift = 64

						if self.lcd.menuNumber == 2:
							Font = self.lcd.currentData
							Justify = self.game.teamsDict[teamG].teamData['justify']
						elif self.lcd.menuNumber == 3:
							Font = self.game.teamsDict[teamG].teamData['font']
							Justify = self.lcd.currentData
						elif self.lcd.menuNumber == 5:
							Font = self.lcd.currentData
							Justify = self.game.teamsDict[teamH].teamData['justify']
						elif self.lcd.menuNumber == 6:
							Font = self.game.teamsDict[teamH].teamData['font']
							Justify = self.lcd.currentData

						FontJustify = (Font-1)*6+Justify-1
						word1 = self.mp.encode(2, 4, 1, 0, 1, 10, 13, 0, 0)
						word2 = self.mp.encode(2, 4, 2, 0, 0, 0, teamAddr + teamAddrShift, 0, 0, pass3_4_flag=True)
						word4 = self.mp.encode(2, 4, 4, 0, 0, 0, FontJustify, 0, '', pass3_4_flag=True)
						# Check data stream insertion
						sendList = [word1, word2, word4, self.MPWordDict[29], self.MPWordDict[30], self.MPWordDict[32]]

		# Make custom sendlist for ASCII to MP ETN send
		if self.serialInputType == 'ASCII' and self.serialInputFlag and self.sp.ETNChangeFlag:  # and not self.ETNSendListFlag:
			self.sp.ETNChangeFlag = False
			self.ETNSendListFlag = True
			# print 'self.sp.ETNChangeFlag'
			self.ETNSendList = []

			if (
					0 and self.sp.guestNameChangeFlag and self.sp.guestFontJustifyChangeFlag
					and self.sp.homeNameChangeFlag and self.sp.homeFontJustifyChangeFlag
			):
				self.sp.guestNameChangeFlag = False
				self.sp.guestFontJustifyChangeFlag = False
				self.sp.homeNameChangeFlag = False
				self.sp.homeFontJustifyChangeFlag = False
				# ETN character change section
				teamsList = []
				FontJustifyList = []
				for team in ['TEAM_1', 'TEAM_2']:
					name = self.game.get_team_data(team, 'name')
					length = len(name)
					pairsList = []
					if length:
						for address in range(int(length/2)):
							leftETNByte = name[address*2]
							rightETNByte = name[address*2+1]
							pairsList.append((leftETNByte, rightETNByte))
							
						if length % 2:
							# Odd Length Ending Section
							leftETNByte = name[-1]
							rightETNByte = 0
							pairsList.append((leftETNByte, rightETNByte))

					else:
						# Blank Name Section
						pairsList.append((' ', 0))
						
					teamsList.append(pairsList)

					Justify = self.game.get_team_data(team, 'justify')
					Font = self.game.get_team_data(team, 'font')
					FontJustify = (Font-1)*6+Justify-1
					FontJustifyList.append(FontJustify)
						
				# print 'teamsList', teamsList
				
				for x, team in enumerate(teamsList):
					# print 'team' , x
					if x == 0:
						teamAddrShift = 0
					elif x == 1:
						teamAddrShift = 64

					for y, pair in enumerate(teamsList[x]):
						leftETNByte = pair[0]
						rightETNByte = pair[1]					
						teamAddr = y+1+teamAddrShift					
						# 0xbc = tunnel code
						# word 2 = address of character pair
						# word 3 = leftETNByte
						# word 4 = rightETNByte or controlByte(if addr = 0or64)
						if rightETNByte == 0:
							rightETNByte = chr(rightETNByte)
						word1 = self.mp.encode(2, 4, 1, 0, 1, 10, 13, 0, 0)
						word2 = self.mp.encode(2, 4, 2, 0, 0, 0, teamAddr, 0, 0, pass3_4_flag=True)
						word3 = self.mp.encode(2, 4, 3, 0, 0, 0, ord(leftETNByte), 0, '', pass3_4_flag=True)
						word4 = self.mp.encode(2, 4, 4, 0, 0, 0, ord(rightETNByte), 0, '', pass3_4_flag=True)
						# Check data stream insertion
						sendList = [word1, word2, word3, word4, self.MPWordDict[29], self.MPWordDict[30], self.MPWordDict[31], self.MPWordDict[32]]
						# self.data2Drivers(sendList)
						self.ETNSendList.append(sendList)
						# print sendList
						
					jword1 = self.mp.encode(2, 4, 1, 0, 1, 10, 13, 0, 0)
					jword2 = self.mp.encode(2, 4, 2, 0, 0, 0, teamAddrShift, 0, 0, pass3_4_flag=True)
					jword4 = self.mp.encode(2, 4, 4, 0, 0, 0, FontJustifyList[x], 0, '', pass3_4_flag=True)
					# Check data stream insertion
					jsendList = [jword1, jword2, jword4, self.MPWordDict[29], self.MPWordDict[30], self.MPWordDict[32]]
					# self.data2Drivers(jsendList)
					self.ETNSendList.append(jsendList)
					# print jsendList
					
			if self.sp.guestNameChangeFlag:
				self.sp.guestNameChangeFlag = False

				# ETN character change section
				name = self.game.get_team_data('TEAM_1', 'name')
				length = len(name)
				pairsList = []
				teamAddrOverride = False
				if length:
					if self.sp.guestNameChangeOneCharFlag:
						self.sp.guestNameChangeOneCharFlag = False
						singleAddr = length/2+length % 2
						addrLength = range(abs(length % 2-1))
						teamAddrOverride = True
					else:
						addrLength = range(int(length/2))
						
					for address in addrLength:
						leftETNByte = name[address*2]
						rightETNByte = name[address*2+1]
						pairsList.append((leftETNByte, rightETNByte))
						
					if length%2:
						# Odd Length Ending Section
						leftETNByte = name[-1]
						rightETNByte = 0
						pairsList.append((leftETNByte, rightETNByte))

				else:
					# Blank Name Section
					pairsList.append((' ', 0))
				
				teamAddrShift = 0
				# print 'len(pairsList', len(pairsList)

				for y, pair in enumerate(pairsList):
					leftETNByte = pair[0]
					rightETNByte = pair[1]					
					if teamAddrOverride:
						teamAddr = teamAddrShift+singleAddr
						# print 'single team addr'
					else:
						teamAddr = y+1+teamAddrShift
						# print 'normal team addr'			
					# 0xbc = tunnel code
					# word 2 = address of character pair
					# word 3 = leftETNByte
					# word 4 = rightETNByte or controlByte(if addr = 0or64)
					if rightETNByte == 0:
						rightETNByte = chr(rightETNByte)
					word1 = self.mp.encode(2, 4, 1, 0, 1, 10, 13, 0, 0)
					word2 = self.mp.encode(2, 4, 2, 0, 0, 0, teamAddr, 0, 0, pass3_4_flag=True)
					word3 = self.mp.encode(2, 4, 3, 0, 0, 0, ord(leftETNByte), 0, '', pass3_4_flag=True)
					word4 = self.mp.encode(2, 4, 4, 0, 0, 0, ord(rightETNByte), 0, '', pass3_4_flag=True)
					# Check data stream insertion
					sendList = [word1, word2, word3, word4, self.MPWordDict[29], self.MPWordDict[30], self.MPWordDict[31], self.MPWordDict[32]]
					# self.data2Drivers(sendList)
					self.ETNSendList.append(sendList)
					# print sendList
					
			if self.sp.homeNameChangeFlag:
				self.sp.homeNameChangeFlag = False

				# ETN character change section
				name = self.game.get_team_data('TEAM_2', 'name')
				length = len(name)
				pairsList = []
				teamAddrOverride = False
				if length:
					if self.sp.homeNameChangeOneCharFlag:
						self.sp.homeNameChangeOneCharFlag = False
						singleAddr = length/2+length % 2
						addrLength = range(abs(length % 2-1))
						teamAddrOverride = True
					else:
						addrLength = range(int(length/2))
						
					for address in addrLength:
						leftETNByte = name[address*2]
						rightETNByte = name[address*2+1]
						pairsList.append((leftETNByte, rightETNByte))
						
					if length % 2:
						# Odd Length Ending Section
						leftETNByte = name[-1]
						rightETNByte = 0
						pairsList.append((leftETNByte, rightETNByte))

				else:
					# Blank Name Section
					pairsList.append((' ', 0))
				
				teamAddrShift = 64
				# print 'len(pairsList', len(pairsList)

				for y, pair in enumerate(pairsList):
					leftETNByte = pair[0]
					rightETNByte = pair[1]
					if teamAddrOverride:
						teamAddr = teamAddrShift+singleAddr
						# print 'single team addr'
					else:
						teamAddr = y+1+teamAddrShift
						# print 'normal team addr'
										
					# 0xbc = tunnel code
					# word 2 = address of character pair
					# word 3 = leftETNByte
					# word 4 = rightETNByte or controlByte(if addr = 0or64)
					if rightETNByte == 0:
						rightETNByte = chr(rightETNByte)
					word1 = self.mp.encode(2, 4, 1, 0, 1, 10, 13, 0, 0)
					word2 = self.mp.encode(2, 4, 2, 0, 0, 0, teamAddr, 0, 0, pass3_4_flag= True)
					word3 = self.mp.encode(2, 4, 3, 0, 0, 0, ord(leftETNByte), 0, '', pass3_4_flag= True)
					word4 = self.mp.encode(2, 4, 4, 0, 0, 0, ord(rightETNByte), 0, '', pass3_4_flag= True)
					# Check data stream insertion
					sendList = [
						word1, word2, word3, word4,
						self.MPWordDict[29], self.MPWordDict[30], self.MPWordDict[31], self.MPWordDict[32]]
					# self.data2Drivers(sendList)
					self.ETNSendList.append(sendList)
					# print sendList
					
			if self.sp.guestFontJustifyChangeFlag:
				self.sp.guestFontJustifyChangeFlag = False

				# ETN FontJustify change section

				Justify = self.game.get_team_data('TEAM_1', 'justify')
				Font = self.game.get_team_data('TEAM_1', 'font')
				FontJustify = (Font-1)*6+Justify-1
									
				teamAddrShift = 0

				jword1 = self.mp.encode(2, 4, 1, 0, 1, 10, 13, 0, 0)
				jword2 = self.mp.encode(2, 4, 2, 0, 0, 0, teamAddrShift, 0, 0, pass3_4_flag=True)
				jword4 = self.mp.encode(2, 4, 4, 0, 0, 0, FontJustify, 0, '', pass3_4_flag=True)
				# Check data stream insertion
				jsendList = [jword1, jword2, jword4, self.MPWordDict[29], self.MPWordDict[30], self.MPWordDict[32]]
				# self.data2Drivers(jsendList)
				self.ETNSendList.append(jsendList)
				# print jsendList
	
			if self.sp.homeFontJustifyChangeFlag:
				self.sp.homeFontJustifyChangeFlag = False

				# ETN FontJustify change section

				Justify = self.game.get_team_data('TEAM_2', 'justify')
				Font = self.game.get_team_data('TEAM_2', 'font')
				FontJustify = (Font-1)*6+Justify-1
									
				teamAddrShift = 64

				jword1 = self.mp.encode(2, 4, 1, 0, 1, 10, 13, 0, 0)
				jword2 = self.mp.encode(2, 4, 2, 0, 0, 0, teamAddrShift, 0, 0, pass3_4_flag=True)
				jword4 = self.mp.encode(2, 4, 4, 0, 0, 0, FontJustify, 0, '', pass3_4_flag=True)
				# Check data stream insertion
				jsendList = [jword1, jword2, jword4, self.MPWordDict[29], self.MPWordDict[30], self.MPWordDict[32]]
				# self.data2Drivers(jsendList)
				self.ETNSendList.append(jsendList)
				# print jsendList
			
			self.ETNSendListLength = len(self.ETNSendList)
		if self.ETNSendListFlag:
			pass# self.printTimesFlag = True
		else:
			self.printTimesFlag = False										
		if self.ETNSendListFlag and self.ETNSendList and not self.checkEventsOverPeriodFlag and self.ETNSendListCount < 1:
			self.sendList = self.ETNSendList[0]
			# print 'self.sendList', self.sendList
			# print 'self.ETNSendList', self.ETNSendList			
			self.ETNSendList.pop(0)
			# print 'self.ETNSendList', self.ETNSendList
			if (self.ETNSendListLength-1) == len(self.ETNSendList):
				self.ETNSendListCount = 3
				# print 'reset count'
		elif self.ETNSendListFlag and not self.checkEventsOverPeriodFlag:
			# Wait for _check_events to settle before sending ETN packets
			self.ETNSendListCount -= 1
		# print 'self.ETNSendListFlag , self.ETNSendList , not self.checkEventsOverPeriodFlag , not self.ETNSendListCount'
		# print self.ETNSendListFlag , self.ETNSendList , not self.checkEventsOverPeriodFlag , not self.ETNSendListCount
			
		if self.checkEventsOverPeriodFlag:
			self.checkEventsOverPeriodFlag = False
		
		# -----End custom sendlist for ASCII to MP ETN send-----

		# Append dirty words to send list
		removeCount = 0
		if len(self.dirtyDict) and not self.ETNSendListFlag:
			for addr in self.priorityListEmech:
				if removeCount <= 8:
					if addr in self.dirtyDict:
						removeCount += 1
						self.sendList.append(self.dirtyDict[addr])
						
						if self.verboseDiagnostic:
							# Print info for dirty words
							group, bank, word, I_Bit, numericData = self.mp.decode(self.dirtyDict[addr])
							print (
								'group', group, 'bank', bank, 'word', word, 'addr', self.mp.gbw_to_mp_address(group, bank, word) + 1,
								'I_Bit', I_Bit, 'data', bin(numericData), bin(self.dirtyDict[addr]))
							
						del self.dirtyDict[addr]
		spaceLeft = 9-removeCount

		# Append remaining words to fill send list
		if self.MP_StreamRefreshFlag and not self.ETNSendListFlag:
			for x in range(spaceLeft):
				if self.game.gameData['sportType'] == 'stat':
					
					self.sendList.append(self.MPWordDict[self.priorityListEmech[self.dataUpdateIndex-1]])
					
					if self.verboseDiagnostic:
						# Print info for remaining words
						print (
							'self.dataUpdateIndex',self.dataUpdateIndex, 'self.priorityListEmech[self.dataUpdateIndex]',
							self.priorityListEmech[self.dataUpdateIndex-1])
						group, bank, word, I_Bit, numericData = self.mp.decode(
							self.MPWordDict[self.priorityListEmech[self.dataUpdateIndex-1]])
						print (
							'group', group, 'bank', bank, 'word', word, 'addr', self.mp.gbw_to_mp_address(group, bank, word) + 1,
							'I_Bit', I_Bit, 'data', bin(numericData), bin(self.MPWordDict[self.priorityListEmech[self.dataUpdateIndex-1]]),
							self.MPWordDict[self.priorityListEmech[self.dataUpdateIndex-1]])
						
					self.dataUpdateIndex += 1
					if self.dataUpdateIndex>len(self.priorityListEmech):
						self.dataUpdateIndex = 1
					
				else:
					
					self.sendList.append(self.MPWordDict[self.dataUpdateIndex])
					# print 'self.dataUpdateIndex',self.dataUpdateIndex
					
					if self.verboseDiagnostic:
						# Print info for remaining words
						group, bank, word, I_Bit, numericData = self.mp.decode(self.MPWordDict[self.dataUpdateIndex])
						print (
							'group', group, 'bank', bank, 'word', word,
							'addr', self.mp.gbw_to_mp_address(group, bank, word) + 1,
							'I_Bit', I_Bit, 'data', bin(numericData), bin(self.MPWordDict[self.dataUpdateIndex]),
							self.MPWordDict[self.dataUpdateIndex])
						
					self.dataUpdateIndex += 1
					if self.dataUpdateIndex > len(self.MPWordDict):
						self.dataUpdateIndex = 1

		if self.verboseDiagnostic or self.ETNSendListFlag:
			pass  # print 'self.sendList', self.sendList, '\nlength', len(self.sendList)

		if not self.ETNSendList:
			self.ETNSendListFlag = False
		else:
			pass  # print 'ETN not done'

		# Create string for transport

		serial_string = ''
		for word in self.sendList:
			first_byte = chr((word & 0xFF00) >> 8)
			second_byte = chr((word & 0xFF))
			serial_string += first_byte+second_byte
		self.serialString = serial_string

		if self.showOutputString:
			print self.serialString


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
