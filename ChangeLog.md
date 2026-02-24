
## SourceBridge 1.4 
**Bug Fixes:**
- Fixed crash if connected AFG31k is running <1.6.5
	- Now SourceBridge disconnects and provides link to firmware upgrade.  

**New Features:**
- New load speed improvements for reused reused waveforms
	- SourceBridge will skip hash check if waveform has not been updated since last transmit.  
- Further improvements to loading speed if only using channel 1.  
	- For setups with short record lengths, setup in ~0.5S is now possible, previously ~4S was minimum.  
#### Known Issues:
- Due to the way that SourceBridge improves load speed through storing the hash of a wfm in its file name.  There is a vanishingly small chance in a extremely specific sequence of events in which the wfm output might not be updated and will use an older wfm version.
	1. Transmit a setup to a connected AFG.
	2. Stop output of AFG.
	3. Modify a waveform in such a way that the hash of the wfm data is unchanged.
		1. Without changing its name or wfm type (Real/I/Q)
	4. Retransmit to the connected AFG.
		Under this sequence of events, SourceBridge will find the wfm to have 'not changed' as the name, type, and hash all match.  Thus will not send the updated wfm, causing the AFG to play an older version of a waveform
	5. This will reveal itself as one of two errors:
		1. If you are using two channels, and the record length of the wfm has changed.  The AFG will throw an error that wfms are inequal length halting SourceBridge.
		2. If you are using one channel, or if the record length has not changed.  The generator will play the older waveform instead of the desired one.  SourceBridge has no way of knowing a hash collision occurred.
	- Workaround: Buy a lottery ticket and restart SoureBridge.  

## SourceBridge 1.3
**Bug Fixes:**
- Launch script would fail if path had a space in it.  
	- Looking at you OneDrive...

**New Features:**
- Waveform data is now hashed, and the hash is stored within the file name on the AFG.  
	- Done to prevent retransmitting large waveforms if contained data is unchanged.
	- 3-5x load speed improvements when reloading long waveforms.

#### Known Issues:
- Due to the way that SourceBridge improves load speed through storing the hash of a wfm in its file name.  There is a vanishingly small chance in a extremely specific sequence of events in which the wfm output might not be updated and will use an older wfm version.
	1. Transmit a setup to a connected AFG.
	2. Stop output of AFG.
	3. Modify a waveform in such a way that the hash of the wfm data is unchanged.
		1. Without changing its name or wfm type (Real/I/Q)
	4. Retransmit to the connected AFG.
		Under this sequence of events, SourceBridge will find the wfm to have 'not changed' as the name, type, and hash all match.  Thus will not send the updated wfm, causing the AFG to play an older version of a waveform
	5. This will reveal itself as one of two errors:
		1. If you are using two channels, and the record length of the wfm has changed.  The AFG will throw an error that wfms are inequal length halting SourceBridge.
		2. If you are using one channel, or if the record length has not changed.  The generator will play the older waveform instead of the desired one.  SourceBridge has no way of knowing a hash collision occurred.
	- Workaround: Buy a lottery ticket and restart SoureBridge.  


## SourceBridge 1.2
**Bug Fixes:**
- Ch1 and Ch2 on AFG would become desynced by >8µS after first load.
- Ch2 ignored trigger commands.
- When stopping playback signal loaded in basic mode would be played out instead of nothing
	- Defaulted to 1MHz sinewave out of both channels
- Fixed issue loading IQ waveforms, where SourceBridge would only send the I.

**New features:**
- Added controls for internal/external ref clocks through SourceExpress


## SourceBridge 1.1
- First released beta
