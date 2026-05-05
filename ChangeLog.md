## SourceBridge_1.5
**Bug Fixes:**
- Sequence Go To END argument now works, previously returned error failing to load sequence.

**New Features:**
- Marker support when using only a single channel.
	- If you have waveform data loaded in only one channel, and enable that channels marker 1.  SourceBridge will now take the marker data from ChannelX Marker1 and put it into the unused channel on the AFG31k.
    - Intended for use with the RADAR plugin as it includes a sync pulse in Marker 1 slot of a compiled pulse train.
    - Can be used to contain Clock and Data within a single waveform for emulating a low speed bus like I2C.

**Changed Features:**
- Using the B-Trigger on Sequences or Standard playback now uses Manual-Trigger instead of defaulting to A-Trigger.
#### Known Issues:
- When using NI-VISA and an IP connection to an AFG.  NI-VISA may be unable to connect to a generator if one of the ip fields contains two characters with a leading 0.
    - Example: 192.168.01.1 - Third field 01 contains two characters and leads with a zero, NI-VISA may be unable to connect to a generator in this case.
    - Workaround: Either do not use leading 0's in defining a connection, or ensure the IP has three characters in each field.
         - 192.168.001.1 and 192.168.1.1 will both work.
     
- When using TekVISA 4.X and a USB connection from SourceBridge to an AFG, SourceBridge will crash due to TekVISA being unable to set a read termination.  
	- Workaround: Use LAN connection, or use the conflict manager to use another VISA for USB connections.  NI-VISA works well here.  

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
