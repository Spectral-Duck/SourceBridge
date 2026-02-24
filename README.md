# What is SourceBridge?
SourceBridge is a python application that acts as a communication layer between Tektronix's SourceXpress and the AFG31k Series.  By using a virtual AWG5200, monitoring its state, then copying its configuration over to a connected AFG31k.  This addresses several pains of using the AFG31k's advanced mode such as:
- Difficulty of manually loading wfms and building sequence table through touch screen.
- Remote UI for AFG31k
	- Tested from Texas to Oregon over VPN, with 2x AFG31ks!
- Unified UI between AWG and AFG.
- Method of running AWG files on AFG (.seqx/.wfmx)
- Easy way of using SourceXpress' plugins with the AFG31k.
	- RADAR plugin is great for SONAR applications.
- Simplifies the use of AFG31k as baseband IQ generator for external modulation
- Easily import IQ data from an RSA306/500/600 for playback.  


# Prerequisites:
- Installed TekVISA
	- Able to communicate with SourceXpress via the GPIB8::1::INSTR connection  
	![SourceXpress connection suscuessful checked through OpenChoiceUtility](/Images/SourceXpressGPIB.png)

# Operating SourceBridge:
- Download SourceBridge.zip from the email
- Unzip to a desired location
- Ensure that GPIB8::1::INSTR is valid. 
	- I use **OpenChoice Instrument Manager** for this.
- Run **Run_SourceBridge.bat**
- Connect a new generator (guide below)
- Drive the AFG31k a if its an AWG! (with limsits, see end of doc)

# Adding a new generator:
Supports all communication methods, LAN, USB, and GPIB
- In SourceXpress press **Connectivity** > **Create Virtual Generator...**  
	![Adding new generator](/Images/GeneratorConnection.png)
- Select the model to be an AWG5202.  
	- Use the 2.5GS/s option, and disable AC output as AC Coupled isn't available on AFG.
	- Using the DCHV output paths allows for the AWG to better replicate the AFG's max amplitudes.
- Recommended config:  
	![Recommended configuration for a virtual generator](/Images/AFG_Config.png)  
> [!IMPORTANT]
> The generator name is what SourceBridge uses to know what VISA ID you want to communicate with.  The only thing that matters is that the VISA ID or an IP address is the last item in the string.  You may also define a generator without a name by only putting the VISA ID in the Name Field.
> - Valid Examples:
>	- TSC's AFG Please don't Break 169.254.3.26
>	- AFG31k-USB USB0::0x0699::0x035E::B010001::INSTR
>	- 10.1.23.4
> - Invalid Examples:
>	- MyAFG10.233.1.1
>		- Missing space between IP and name
>	- 10.233.1.2 MyFancyAFG
>		- VISA ID is not last item in string.  
> - Any names that are not recognized will be ignored.
>	- Means you can control an AFG31k simultaneously with your AWG5200/70k.
>	- If you mistype the generator name, **don't rename it** delete the generator and make a new one.  (Due to bug with the PI when renaming generators)<div style="page-break-after: always;"></div>

# Unsupported or Beyond scope:
- Do not use SourceXpress programmatically while using SourceBridge. - Unsupported
	- SourceBridge requires the use of polling the SourceXpress's run state and active generator.  There _will_ be a VISA collision. 
- Do not open SignalVu-PC on the same system as SourceXpress.  - Unsupported
	- SE and SVPC both use GPIB8::1::INSTR to communicate via SCPI.
	- Unknown which will dominate the interface breaking communication.
- Per Channel Sequences - Unsupported
	- Use Multi Tracked Sequences
- At runtime digital IQ modulator - Unsupported
	- IQ wfms can be converted to real with SourceXpress Capture/Playback tool 
	- I and Q wfms can individually be assigned to channels though
	- I and Q tracks of a sequence also can be assigned to channels
	- Use an external IQ Mixer to upconvert for >250MHz.  TSG4106A works well. 
- Mixed Sequence and Wfm Playback - Unsupported
- Wfms of Different Length - Unsupported
- Per Channel Trigger Conditions - Unsupported
- Basic Mode Controls? - Beyond Scope
	- SourceXpress' AFG mode is too different from the AFG's basic mode to cleanly integrate this way. To get the most out of the AFG31K's basic mode would require a dedicated application.
		- Use Kickstart/ArbExpress for basic controls.
- Per Channel Sample Rate - Unsupported


> That is way slicker than it should be  
~ Coworker
