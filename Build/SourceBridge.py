import pyvisa
import re # regular expressions
import time
import struct # for binary handeling
import os
import numpy as np
import random
import inspect
import datetime 
     
#https://download.tek.com/manual/AWG5200-Programmer-Manual-077133700-RevA.pdf                   - AWG Programmers
#https://download.tek.com/manual/SourceXpress-Printable-Help-Document-077114505.pdf             - AWG Help - Page 119 WFMX format 
#https://download.tek.com/manual/SourceXpress-Programmer-Manual-077114405.pdf                   - SE  Programmers
#https://www.tek.com/-/media/documents/077148803_afg31000_series_programmersmanual_nov2020.pdf  - AFG Programmers
# Shouldn't have to touch these, but here are the valid AFG models for this program.
valid_ids = [
    'AFG31252',
    'AFG31251',
    'AFG31152',
    'AFG31152',
    'AFG31102',
    'AFG31101',
    'AFG31101',
    'AFG31052',
    'AFG31051',
    'AFG31022',
    'AFG31021',
]

def ErrorChecking(AWG,AFG):
    """
    Accepts: 
        AWG_Object (VISA OBJECT) - Required to be SourceXpress 
        AFG_Object (VISA OBJECT) - Target AFG31k object
    Returns:
        If setup is valid for AFG:
            Mode, Ch1.ChannelContents, Ch2.ChannelContents  
        else:
            0 - Indiciating load failure.  

    A Giant If tree that will validate that the setup in SourceXpress is valid for use on an AFG31k...
    I am not a programming expert, if someone has a better approach for this go forth and conquer.
    """
    start = time.time() # timing measurment debug use.
    # these values are the default for any AFG31k, but the licenses enabled on the instrument may increase some of these.
    Max_Sr = 250e6 
    Max_Rl = 16e6
    Max_Steps = 256
    SubSequence = False  
    Load_Failure = False # setup compile fail flag. 
    # Chose a flag to indicate bad seutp instead of exceptions for each.  This way I could print out all the errors at once.
    # Instead of the user needing to hit compile 3-4 diffrent times to resolve each.  
    Mode = None


    # Communicate with the AFG and get what licenses are present, that will set the MAX SR and memory depth
    Licenses = AFG.query('LICense:LIST?')
    BW = int(re.sub(r'[a-zA-Z]','',AFG.ID)[2:-1]) #use regular expressions to discard any lettters (accounts for future B/C models)
        # Discard first two and last number, Series and channel count respectively.  Not going to deal with 1 ch units with this code.
        # Assume all instruments are 2 channel, and that the user wont put something in CH2 that shouldn't be.  Not a good idea but meh.

    # Remember this just sets the limits for what the AFG can playback.
    # Changing these will just break the error checker, not make your AFG better.
    if 'DEMO' or 'TRIAL' in Licenses: #Using either a demo or trial license fully unlocks insturment.
        print('AFG equipted with demo license, fully unlocked')
        Max_Sr = 2e9
        Max_Rl = 128e6
        # 20MHz is default, no need to test
    # Bandwidth config
    if BW == 5:       # 50MHz
        Max_Sr = 500e6
    elif BW == 10:      # 100MHz
        Max_Sr = 1e9
    elif BW == 15 or 25: #150/250MHz
        Max_Sr = 2e9    
    # Memory test
    if 'MEM' in Licenses: # do we have the extended memory license
        Max_Rl = 128e6

    Ch1 = ChannelContents()
    Ch2 = ChannelContents()
    Sequence_Data = []

    Ch1.SampleRate = float(AWG.query(f'CLOCk:SRATe?'))
    if Ch1.SampleRate > Max_Sr:
        log.warn(f'Set Sample Rate excedes AFG31k\'s max, got {Ch1.SampleRate}.  Clamping to max: {Max_Sr}. Go to SETUP > CLOCK to resolve. ')
        Ch1.SampleRate = Max_Sr  #trunkate the SR and continue.
        #Load_Failure = True 
        # Not sure if this one should cause a load failure...
        # On one hand, possible to still play at a lower SR, but the output will be wrong... Thoughts?  implicit errors...
    

    Ch1.type = AWG.query('Source1:Casset:Type?')
    Ch2.type = AWG.query('Source2:Casset:Type?')
    Ch1.casset = AWG.query('Source1:Casset?').replace('"','').split(',')
    if len(Ch1.casset) == 1 and Ch1.casset[0] != '': Ch1.casset.append('Real')
    Ch2.casset = AWG.query('Source2:Casset?').replace('"','').split(',')
    if len(Ch2.casset) == 1 and Ch2.casset[0] != '': Ch2.casset.append('Real')
    Ch1.resolution = int(AWG.query('SOURCE1:DAC:RESOLUTION?'))
    Ch2.resolution = int(AWG.query('SOURCE2:DAC:RESOLUTION?'))
    

    """
    Previously setting the output amplitude was done right before playback, now it matches the rest of the program aproach
    The amplitudes are read here, and any conflicts are handled.  
    Additonally, this allows the amplitudes to be modified if needed later in the program (see marker support)
    """
    Ch1.offset = float(AWG.query('SOURCE1:VOLTAGE:LEVEL:IMMEDIATE:OFFSET?')) 
    Ch2.offset = float(AWG.query('SOURCE2:VOLTAGE:LEVEL:IMMEDIATE:OFFSET?')) 
    Ch1.amplitude = float(AWG.query('SOURCE1:VOLTAGE:LEVel:IMMediate:AMPLITUDE?'))
    Ch2.amplitude = float(AWG.query('SOURCE2:VOLTAGE:LEVel:IMMediate:AMPLITUDE?'))
    Ch1.amplitude = AFG_Scale_Amplitude(Ch1.offset, Ch1.amplitude, '1')
    Ch2.amplitude = AFG_Scale_Amplitude(Ch2.offset, Ch2.amplitude, '2')

    # This code is for adding marker support to the program!
    # Checks if oone channel is used, if that channel has markers enabled, and if the other channel is unused.
    if Ch1.casset[0] != '' and Ch2.casset[0] == '' and Ch1.resolution < 16: 
        Ch2.casset = Ch1.casset.copy()
        Ch2.casset[-1] = 'Marker'
        Ch2.amplitude = AWG.query('SOURce1:MARKer1:VOLTage:LEVel:IMMediate:AMPLitude?')
        Ch2.offset = AWG.query('SOURce1:MARKer1:VOLTage:LEVel:IMMediate:OFFSet?')
        log.debug('Ch1 Marker')
    elif Ch2.casset[0] != '' and Ch1.casset[0] == '' and Ch2.resolution < 16:
        Ch1.casset = Ch2.casset.copy()
        Ch1.casset[-1] = 'Marker'
        Ch1.amplitude = AWG.query('SOURce2:MARKer1:VOLTage:LEVel:IMMediate:AMPLitude?')
        Ch1.offset = AWG.query('SOURce2:MARKer1:VOLTage:LEVel:IMMediate:OFFSet?')
        log.debug('Ch2 Marker')

    # Ensures that we use a valid configuration.  If they are the same, its implied fine
    # If they are not, and If both are not both NONE type, then one is a SEQ and one a WAV, thus invalid.
    # All other combinations okay.
    if Ch1.type == Ch2.type:
        Mode = Ch1.type
    elif Ch1.type != 'NONE' and Ch2.type != 'NONE':
        log.error(f'Invalid Setup, cannot mix Sequence and Standard playback on AFG31k')
        Load_Failure = True
    else: #not sure how else to approach this... not fond of the sloution.
        # Essentally sets the type to whichever is not NONE.
        if Ch1.type == 'NONE':
            Mode = Ch2.type
        else: Mode = Ch1.type

    Ch1.timer = float(AWG.query("TRIGger:INTerval?"))
    if Ch1.timer < 2e-6:
        log.warn(f'Interal trigger interval below AFG31k\'s min got {Ch1.timer}.  Clamping to 2uS, go to Setup > Trigger > Internal Trigger Interval to fix.')
        Ch1.timer = 2e-6

    # Check and save the clocking type if valid
    Ch1.Clock = (AWG.query("CLOCk:SOURce?"))
    log.info(f'AWG Clocking: {Ch1.Clock}')
    if Ch1.Clock == 'EFIX':
        Ch1.Clock = 'EXT'
        log.warn(f'If the AFG cannot lock to an external REF there will be small freq distortions every 1/10s.')
        log.warn('SourceBridge cannot detect clocking errors on AFG31k.')
    elif Ch1.Clock == 'EVAR' or Ch1.Clock == 'EXT':
        # If its either External Clocked, or Variable Ref they are invalid, throw warning.
        log.warn(f'Only supported clocking types on AFG31k are Internal Ref or External Ref, defaulting to Internal Ref')
        Ch1.Clock = 'INT'
    
    if Mode == 'WAV': # Check for Waveform specific error conditions
        # Ensure loaded wfms are not of diffrent length.
        if Ch1.type == 'WAV': Ch1.length = int(AWG.query(f'WLISt:WAVeform:LENGth? "{Ch1.casset[0]}"'))
        if Ch2.type == 'WAV': Ch2.length = int(AWG.query(f'WLISt:WAVeform:LENGth? "{Ch2.casset[0]}"'))
        if Ch1.type == Ch2.type and Ch1.length != Ch2.length: # If both are WAV, we need to check if their lengths match.  b
            log.error(f'Waveform loading failed. AFG31k does not support waveform of diffrent lengths.') 
            Load_Failure = True
        if Ch1.length > Max_Rl or Ch2.length > Max_Rl:
            log.error(f'Waveform loading failed. Insufficent memory, >{Max_Rl}Samples used.')
            Load_Failure = True

        # Trigger modes!
        Ch1.trigger = AWG.query('SOURce1:RMODe?')
        Ch2.trigger = AWG.query('SOURce2:RMODe?')
        Ch1.trigger_source = AWG.query('SOURCe1:TINPut?')
        
        log.info(f'Trigger Source: {Ch1.trigger_source}')

        if Ch1.trigger != Ch2.trigger:
            log.warn('AFG does not support per channel triggers, defaulting to Ch1 Trigger.')
        if Ch1.trigger_source == 'BTR': 
            log.info(f'AFG Does not have B trigger, SourceBridge changes this to USER trigger.')
            Ch1.trigger_source = 'MAN'
            

    elif Mode == 'SEQ': # Check for the Sequence mode specific error conditions

        # if the Sequence Names dont match, and neither are NONE type, then we are using two diffrent sequences which is unsupported.
        # Throw a load failure and continue checking.  
        Sequence_Name = ''
        Steps = 0
        if Ch1.casset[0] != Ch2.casset[0] and Ch1.type != 'NONE' and Ch2.type != 'NONE':
            log.error(f'Sequence loading failed.  Multi-sequencing is not supported on AFG31k, instead use a multi-tracked sequence.')
            Load_Failure = True
        else:
            if Ch1.casset[0] != '': Sequence_Name = Ch1.casset[0]
            else: Sequence_Name = Ch2.casset[0]

            #print(f'SequenceName: {Sequence_Name}')
            Steps = int(AWG.query(f'SLISt:SEQuence:LENGth? "{Sequence_Name}"'))
            if Steps > Max_Steps:
                log.error(f'Sequence loading failed.  Sequence: "{Sequence_Name}" has {Steps}, max of {Max_Steps}')
                Load_Failure = True


            
            for step in range(Steps):
                index_type = AWG.query(f'SLISt:SEQuence:STEP{step+1}:TASSet1:TYPE? "{Sequence_Name}"')
                if index_type != "WAV":
                    SubSequence = True
        
        if SubSequence: 
            log.error(f'Sequence loading failed.  SubSequencing not supported by AFG31k')
            # TODO: Build logic for checking if a sequence can be unpacked/flattend here.  
            # Untill that happens, this is a non supported opperating mode. 
            Load_Failure = True
        
        else: # Assuming subsequencing was not found now we can go through 
            log.debug(f'Ch1 Casset: {Ch1.casset}, len: {len(Ch1.casset)}')
            log.debug(f'Ch2 Casset: {Ch2.casset}, len: {len(Ch2.casset)}')
            log.debug(f'Ch1 Type: {Ch1.type}')
            # Chx.casset[1] will give the track number
            # need to ONLY get data from the tracks used.
            log.debug(f'Steps: {Steps}')
            BTrig_Flag = False
            EndFlag = False
            for i in range(1,Steps+1):
                message = ""
                message = message + f'SLISt:SEQuence:STEP{i}:WINPut? "{Sequence_Name}"; :SLISt:SEQuence:STEP{i}:RCOunt? "{Sequence_Name}"; :SLISt:SEQuence:STEP{i}:EJINput? "{Sequence_Name}"; :SLISt:SEQuence:STEP{i}:EJUMp? "{Sequence_Name}"; :SLISt:SEQuence:STEP{i}:GOTO? "{Sequence_Name}"'
                reply = AWG.query(message).replace('"','')
                if 'BTR' in reply: 
                    reply = reply.replace('BTR', 'MAN')
                    BTrig_Flag = True
                if 'END' in reply: # END not supprted by firmware on AFG, but just replacing it with the length of the sequence has the same affect. 
                    reply = reply.replace('END',f'{Steps}')
                    

                # Read the waveform data from the sequencer, and append the wfm type I/Q or Real(None type)
                reply = reply.split(';')
                if len(Ch1.casset) != 1:
                    if Ch1.casset[1] != 'Marker':
                        temp = AWG.query( f'SLISt:SEQuence:STEP{i}:TASSet{Ch1.casset[1]}? "{Sequence_Name}"').replace('"','')
                        format = 'Real'
                        if len(Ch1.casset) == 3:  format = Ch1.casset[2]
                    
                    elif Ch1.casset[1] == 'Marker':
                        temp = AWG.query(f'SLISt:SEQuence:STEP{i}:TASSet{Ch2.casset[1]}? "{Sequence_Name}"').replace('"','')
                        format = 'Marker'
                    reply.append([temp,format])

                if len(Ch2.casset) != 1:
                    if Ch2.casset[1] != 'Marker':
                        temp = AWG.query(f'; :SLISt:SEQuence:STEP{i}:TASSet{Ch2.casset[1]}? "{Sequence_Name}"').replace('"','')
                        format = 'Real'
                        if len(Ch2.casset) == 3:  format = Ch2.casset[2]
                    
                    if Ch2.casset[1] == 'Marker':
                        temp = AWG.query(f'SLISt:SEQuence:STEP{i}:TASSet{Ch1.casset[1]}? "{Sequence_Name}"').replace('"','')
                        format = 'Marker'
                    reply.append([temp,format])
                    
                #print(f'Reply: {reply}')

                # print(f'Reply {i}: {reply}')

                ## attach I and Q suffixes to the used wfm, so that we know what to grab later.  
                #if len(Ch2.casset) == 3: 
                #    reply[-1] = [reply[-1],Ch2.casset[2]]
                #    if len(Ch1.casset) == 3: reply[-2] = [reply[-2],Ch1.casset[2]]
                #elif len(Ch1.casset) == 3:  reply[-1] = [reply[-1],Ch1.casset[2]]

                Sequence_Data.append(reply)
            # While not supported by the AFG's firmware, adding an End Jump was easy enough.  
            # Just jump to the end... not sure why I didn't add this previously but meh.
            # Removing error flag.
            #if EndFlag:
            #    print('ERROR: Jumpto/Goto END not supported on AFG31k.')
            #    Load_Failure = True
            if BTrig_Flag:print('INFO: B Trigger found in Sequencer, changing to Manual.')
            #for i in range(len(Sequence_Data)): # Debug to print contents of sequence data to terminal
            #    print(Sequence_Data[i])    

    
    elif Mode == 'NONE': 
        log.error('No data loaded in channels, unable to playback.')
        Load_Failure = True
    
    if Load_Failure:
        log.error('Due to unsupported elements, signal cannot be loaded. Aborting wfm Transfer.')
        log.info(f'ErrorChecking Execution time: {round(time.time()-start,3)}S')
        return(0)
    else:
        return(Mode,Ch1,Ch2,Sequence_Data) # return the parameters read as part of the setup.

def AFG_Scale_Amplitude(Offset, Scale, channel_number = 'Null'):
    if abs(Offset) + Scale/2 > 2.5:
        Scale = (2.5-abs(Offset))*2
        log.warn(f'CH{channel_number} Scale + Offset Exceded AFG31k\'s capability, output scale will be clamped to: {round(Scale,3)}Vpp + {Offset}Voffset')
    return(Scale)

def create_tfw(waveform, thumbnail=True):
    """write target file in TFWX format with waveform"""
    w = np.array(waveform, dtype=np.float32)
    amp = w.max() - w.min()
    off = w.min() + (amp / 2)
    normal = (w - off) * 65528/amp
    n = np.array(normal, dtype=np.int16)
    samples = len(n)
    header = bytearray(512)
    struct.pack_into('<9s7x2Ii', # format
                     header,                                    # buffer
                     0,                                         # offset
                     b'TEKAFG30K', # magic bytes
                     20050114,                                  # version
                     samples,                                   # length
                     int(thumbnail))                            # envelope flag
    if thumbnail:
        # an envelope vector is used for arb plot on AFG
        envelope = envelope_vector(n)
        header[28:28+len(envelope)] = memoryview(envelope)
    struct.pack_into('2d',      # format
                     header,    # buffer
                     440,       # offset
                     amp,       # amplitude
                     off)       # offset
    return(header + memoryview(n))
    
    #with open(target, 'wb') as f:
    #    f.write(header)
    #    f.write(memoryview(n))

def envelope_vector(normal):
    """return envelope vector from normalized int16 values"""
    # envelope is maximum 206 uint8 min-max pairs
    n = np.array((normal >> 8) + 128, dtype=np.uint8)
    if len(n) <= 206:
        upper = n
        lower = n
    else:
        segments = np.array_split(n, 206) # does not overlap, need overlapping segments
        upper = np.zeros(206, dtype=np.uint8)
        lower = np.zeros(206, dtype=np.uint8)
        for i, s in enumerate(segments):
            upper[i] = s.max()
            lower[i] = s.min()
    c = np.vstack((lower, upper)).reshape(-1, order='F')
    return c

def transfer_waveform_file(instrument, filename, file_contents):
    """
        transfer_waveform_file transfers a waveform file (.tfwx) to an AFG31k

        :param instrument: PyVISA resource object
        :param filename: filename of waveform file
        :param file_contents: contents of waveform file
        :return: none
    """ 

    #filename = filename.replace('-','')
    
    chunk_size = 1048575 # size of each binary data chunk in bytes (max allowed is 1048575 bytes)
    total_size = len(file_contents) # get number of bytes in file
    num_chunks = (total_size // chunk_size) + (1 if total_size % chunk_size != 0 else 0) # get number of chunks required to send entire file
    instrument.write('MMEMory:CDIRectory "M:/"')
    command = f'DATA:FILE "{filename}",{total_size},' # SCPI command to transfer file
    #command = f'DATA:FILE "WFM.tfwx",{total_size},' # SCPI command to transfer file
    

    # send wavefrom file
    for i in range(num_chunks):
        
        # get binary chunk from file contents
        start = i * chunk_size
        end = start + chunk_size
        chunk = file_contents[start:end]
        log.info(f"Sending chunk {i+1}/{num_chunks}, size: {len(chunk)} bytes")
        # Yes this is an easter egg... if you find this congrats?  I think?
        if i>100 and random.random()>0.999:
                print('Large wfm, I hope you had some coffee..\r',end='')
        instrument.write_binary_values( command,chunk, datatype='b') # transfer waveform
        
        if(i == 0 or i ==1): # check for errors with DATA:FILE command
            error = instrument.query("SYST:ERROR?")
            if(error[0] != "0"):
                raise Exception(f"DATA:FILE command error, {error}")
      
    # check if waveform file was saved succesfully
    savedFiles = instrument.query("MMEMory:CATalog?")
    if f"{filename}" not in savedFiles:
        #print(f"All Saved Files:\n{savedFiles}")
        raise Exception("Waveform file transfer failed") 
    
    log.info("File sent successfully.")
    instrument.query('*OPC?')

def get_SE_wfm_saved(instrument, wfm_name, wfm_type = None):
    """
    Accepts:
        Instrument (VISA OBJECT) - Required
        wfm_name (String) - Required
    Returns: 
        data from wfm_name.

    Insturcts SourceXpress to save the waveform to the disk in a binary format.
    Reads data from the wfm file

    """
    data = []
    base_path = 'C:\\Temp\\SourceBridge'
    if not os.path.isdir(base_path): os.makedirs(base_path) # If path does not exist, make it

    #print(f"Waveform name: {wfm_name}")
    length = int(instrument.query(f'WLISt:WAVeform:LENGth? "{wfm_name}"'))

    path = base_path + f"\\{wfm_name}.wfmx"
    #print(wfm_name)
    #print(path)
    instrument.write(f'MMEMory:SAVE:WAVeform:WFMX "{wfm_name}","{path}"')
    instrument.query("*OPC?")
    #while not os.path.isfile(path):
    #    pass
    file = open(path,'r',encoding='latin-1')
    line = file.readline()
    file.close()
    # This gets the offset its very hacky, but functional... it wont work long term.
    # TODO: MAKE LESS SHIT WAY OF FINDING OFFSET.
    line = line.replace('<DataFile offset="','')
    data_offset = int(line.replace('" version="0.2">',''))

    file = open(path,'rb')
    is_binary = False

    if wfm_type == 'Real' or wfm_type == 'I':# If real or I wfm, just use the dataoffset. 
        file.seek(data_offset)
        
    elif wfm_type == 'Marker': # only going to deal with pulling M1 in this case, thus is 
        querried_type = instrument.query(f'WLISt:WAVeform:SFORmat? "{wfm_name}"')
        if querried_type == 'REAL':
            file.seek(data_offset+4*length)
        else:
            file.seek(data_offset+8*length)
        is_binary = True
    else: # Q wfm is the weird one, its placed after the I data  
        file.seek(data_offset+4*length)

    if not is_binary:
        for i in range(length):
            data.append(float(struct.unpack("f",file.read(4))[0]))
    #print(len(data))
    else:
        for i in range(length):
            # grabs the data from the M1 index as either -1 for 0 and 1 for 1
            # the  *2-1 rescales 0 to 1 to -1 to 1, feels a bit hacky but works well.
            data.append((int(struct.unpack('=?',file.read(1))[0]))*2-1)
    
    file.close()
    file = open(f'{base_path}\\{wfm_name}_{wfm_type}.csv','w')
    for i in range(len(data)):
        file.write(f'{i},{data[i]}\n')
    file.close()
    os.remove(path)
    return(data)

def ESR(afg):
    """
    Accepts: 
        Instrument (VISA OBJECT) - Required to be AFG
    Returns:
        Nothing.

    Queries the AFG's ESR, if non-zero will read out all errors.
    Will pause program execution for user intervention
    """

    flag = False
    error = afg.query("SYST:ERROR?")
    while error[0] != '0':
        print(f'Error: {error}')
        error = afg.query("SYST:ERROR?")
        flag = True

    if flag:
        print('Continue opperation? (y/n): ',end='')
        reply = input()
        if 'y' not in reply.lower():
            print('Terminating program.')
            quit()

def long_OPC(instrument, timeout = 30):
    """
    Accepts: 
        Instrument (VISA OBJECT) - Required to be AFG
        timeout  - max waiting time, 30 seconds default
    Returns:
        Nothing.

    Handles long OPC requests without requiring changing the timeout.  
    Useful for processes that take a while, such as compiling/loading wfms.
    If timeout is exceded, the program will halt for user intervention.
    """
    end_time = time.time()+timeout
    flag = False
    instrument.write('*OPC?')
    while end_time > time.time():
        try: 
            instrument.read()
            flag = True
            break
        except: pass
    # if the while loop ends without flipping the flag, we have exceded timeout instrument nonresponsive.  
    if not flag:
        reply = input(f"AFG timedout {timeout}S elapsed, continue opperation?  (y/n):")
        if 'y' not in reply.lower():
            print('Terminating program.')
            quit()


def afg_innitalization(instrument):
    """
    Accepts: 
        Instrument (VISA OBJECT) - Required
    Returns:
        Nothing.
    
    Ensures the connected AFG is ready for SourceBridge to take over.
        Resets instrument to clear old settings.
        Sets to Advanced Mode 

    """    

    
    start = time.time()
    log.info('Innitializing the connected AFG...')
    # Considered using SYSTem:KLOCk to lock the AFG's front pannel while the script is attached.  
    # However, SYSTem:KLOCk does not lock the Touchscreen, only the buttons.  
    # Meaning user could still cause issues by switching playback modes during opperation... 
    # Choosing to omit lockout, but will expect user to NOT mess with the AFG while SB is cotrolling it.
    # Granted, the ESR macro should catch when this happens  
    instrument.write('*RST')

    # Removing DC settings, makes innitialization faster 
    # was workaround for issue where AFG would go into basic mode after ending a triggered playback for a short peroid of time.
    # Also removing this code addresses bug with AFG31k, where if Basic mode amplitude is <=500mVpp, it locks the advanced mode amplitude to the basic mode.
    #   DC Wfms implicilty set the output amplitude to 10mVpp, thus locks the advanced mode's output to 10mVpp. This was fun to discover...
    # Now opening relays to prevent Basic mode from excaping.  
    #instrument.query('*OPC?')
    #instrument.write('SOURce1:Function:Shape DC')
    #instrument.query('*OPC?')
    #instrument.write('SOURce2:Function:Shape DC')
    long_OPC(instrument)
    AFG_Clean_Up(instrument)
    instrument.write('SEQControl:STATe 1') # ensure the AFG31k is using the advanced mode.  
    instrument.query('*OPC?')
    log.info(f'AFG innitalization finished, processing time: {round(time.time()-start,3)}')

def transfer_wfm(SourceXpress,AFG,wfm,catalog):
    # print(f'wfm transfer: {wfm}')
    """
    Will transfer any wfms in the wfm object from SE to AFG.
    Wfm must be passed as the name of the waveform in SourceXpress

    Will return the hashed name generated for this wfm.
    """
    if len(wfm) == 1:
        wfm = wfm[0]
        wfm_type = 'Real'
    else:
        wfm, wfm_type = wfm
    #start = time.time()
    # Create the short name of the waveform, used for the local cashe
    #   Example: Test_Real, or Vector_I - Used as a key for that waveform in the local dict.
    wfm_short_name = f'{wfm}_{wfm_type}'
    """
    Concept: if a wfm file is older than the last time IT was transfered, dont even perform the saving/hasing process.
    Should further improve loadtimes for reused long wfms

    Cannot use a single timestamp to index the whole process, MUST be done on a per wfm basis see timeline:
      Wfm A+B Created    Wfm A Modified 
    _________|_______________|__________________________________-> time
                  |               |               |              
            Wfm A loaded     Wfm B Loaded     Wfm A Loaded**
                           Wfm A NOT Loaded!       

    **
        Under this setup using a single generator update timestamp
        Wfm A would not be loaded a second time as it's update timestamp would be older than the last update.
        Resulting in an older wfm being used instead.
    **

    If wfm is newer than its timestamp, or if not in the dictonary.
        Run Hash + Transfering process
        Save the hash name + new timestamp as entry in dictonary.

    dictonary entry:
    "wfm_name" : [hashed_name, wfm_update_time_stamp (last transfer)]
    """
    # Grab the timestamp of the wfm and convert to seconds since epoch.  
    wfm_time = SourceXpress.query(f'WLIST:WAVEFORM:TSTAMP? "{wfm}"').replace('"','').replace('\n','')
    wfm_time = datetime.datetime.strptime(wfm_time,'%Y/%m/%d %H:%M:%S').timestamp()


    # Check if waveform to be transmitted is in the dictornary 
    if wfm_short_name in AFG.wfm_dict and AFG.wfm_dict[wfm_short_name][1] > wfm_time:
        # if wfm is already known, we do NOT transmit NOR check hash, we recall the old name and continue.
        log.info(f'Waveform: "{wfm}" not updated since last transfer, skipping hash check.')
        wfm_name = AFG.wfm_dict[wfm_short_name][0]
    else: 
        # wfm unknown, or if wfm has been updated since the last transfer we must check the hash.
        # Get wfm data from SourceXpress
        data = get_SE_wfm_saved(SourceXpress,wfm,wfm_type)
        # generate the hash of the wfm data used in cataloging.
        # This method of hashing the wfm DOES have a vanishngly small chance of hash collision.
        #   IE, if user defines wfm, transmits wfm, stops afg output, then changes the wfm in a VERY specifc way such that the hash of the wfm does not change.
        #   Yes, SourceBridge will not update the AFG's output, and it will use the old wfm.  
        #   If the new wfm is of diffrent size, and its in a multi tracked seq it will crash due to mismatched wfm lengths.
        # I am making the choice here to not build additonal checks for this.  
        # A 5x loadspeed improvement is much more valuable than the functionially zero % chance of this occuring.  
        # NOTE: Python *apparently* uses SipHash, unsure the validity of this as I could not find it in the docs.
        #           Found this in a blog by Andrew Brookins.  
        # TIL: Pythons hash is 'salted' with random values between python instsances...
        #         My understanding of this is that instance to instance of sourcebridge the hash might change.
        #           Not really an issue since default behavior is to nuke the AFG's memory and start fresh each time anyways.  
        data_hash = hash(tuple(data))

        # convert to tfw format for the AFG.
        data = create_tfw(data)

        # Determine wfm name
        wfm_name = f'SB_{wfm}_{wfm_type}_{data_hash}.tfwx'

        # If wfm is not already on the AFG, transmit.  Otherwise pass
        if wfm_name not in catalog:
            log.info(f'Waveform: "{wfm}_{wfm_type}" not on AFG, transfering')
            transfer_waveform_file(AFG,wfm_name,data)
        else:
            log.info(f'Waveform: "{wfm}" matches hash on AFG, skipping transfer')

        # update the local dictonary as to the wfms hashed name + current time to know it was updated.
        AFG.wfm_dict[wfm_short_name] = [wfm_name,time.time()]



    # On the AFG import the wfm from memory to the Sequencer.
    AFG.write(f'WLISt:WAVeform:IMPort "{wfm_name}"')

    AFG.query('*OPC?')
    #print(f'Waveforms transfered to AFG, processing time: {round(time.time()-start,3)}')
    return(wfm_name)

def Transfer_Setup(SourceXpress,AFG,Setup):
    """
    Accepts: 
        SourceXpress (VISA OBJECT) 
        AFG (VISA OBJECT)
        Setup (ErrorChecking Object)
    returns:
        1 if successful
        0 if unsuccessful
    """
    Mode, Ch1, Ch2, Sequence_Data = Setup # unpack.  



    if Mode == 'WAV':
        # system is configured to run in the non sequenced mode
        # 
        # Set the output mode to match Ch1.trigger
        # Set the trigger polarity
        # Set the timer
        # Move Waveform(s) over.
        # Assign Wfms to channels
        # Set vertical Scale
        # Set Sample Clock
        # Enable Output 
        # return 0

        # Setting Output mode must happen first, it clears the wfm list.
        # Trigger continious (TCON) can be created via the gated mode, with setting the jump event to Manual
        log.info(f'Trigger Mode: {Ch1.trigger}')
        if Ch1.trigger == 'TCON':
            AFG.write('SEQControl:RMODe GATEd')
            AFG.write('SEQuence:ELEM1:JUMP:EVENt Manual') # Intresting workaround, 
            # AFG 'Triggered Contious' opperating mode.
            # Though using the gated mode, and set the disarm to user input it acts the same!
        else: 
            AFG.write(f'SEQControl:RMODe {Ch1.trigger}')

        #print(f'Ch1 Casset: {Ch1.casset}')
        #print(f'Ch2 Casset: {Ch2.casset}')

        # Transfer waveforms over to the AFG
        catalog = AFG_Get_Catalog(AFG)
        if Ch1.casset[0] != '': 
            Ch1.wfm_name = transfer_wfm(SourceXpress,AFG,Ch1.casset,catalog)
        if Ch2.casset[0] != '':
            Ch2.wfm_name = transfer_wfm(SourceXpress,AFG,Ch2.casset,catalog)

        #print(f'Transfering: {wfms_to_transfer}')
        #transfer_wfm(SourceXpress,AFG,wfms_to_transfer)
        
        # Load data into AFG Outputs
        if Ch1.casset[0] != '':
            AFG.write(f'SEQuence:ELEM1:WAVeform1 "{Ch1.wfm_name}"')
            #if len(Ch1.casset) == 1:
            #    AFG.write(f'SEQuence:ELEM1:WAVeform1 "SB_{Ch1.casset[0]}.tfwx"')
            #else:AFG.write(f'SEQuence:ELEM1:WAVeform1 "SB_{Ch1.casset[0]}_{Ch1.casset[1]}.tfwx"')
        if Ch2.casset[0] != '':
            AFG.write(f'SEQuence:ELEM1:WAVeform2 "{Ch2.wfm_name}"')
            #if len(Ch2.casset) == 1:
            #    AFG.write(f'SEQuence:ELEM1:WAVeform2 "SB_{Ch2.casset[0]}.tfwx"')
            #else:AFG.write(f'SEQuence:ELEM1:WAVeform2 "SB_{Ch2.casset[0]}_{Ch2.casset[1]}.tfwx"')
        AFG.query('*OPC?') # Wait for system to catch up

        
        ESR(AFG)
        if Ch1.trigger != 'CONT':
            log.info(f'Trigger Source: {Ch1.trigger_source}')
            if Ch1.trigger_source == 'ITR': # internal trigger
                AFG.write('SEQuence:ELEM1:TWAit:EVENt TIMer')
                AFG.write(f'SEQControl:TIMer {Ch1.timer}')
            elif Ch1.trigger_source == 'MAN':
                AFG.write('SEQuence:ELEM1:TWAit:EVENt MAN')
            else:
                slope = SourceXpress.query('TRIGGER:SLOPE? ATRIGGER')
                AFG.write('SEQuence:ELEM1:TWAit:EVENt EXT')

                if slope == 'POS':
                    AFG.write('SEQuence:ELEM1:TWAit:SLOPe POS')  
                    AFG.write('SEQuence:ELEM1:JUMP:SLOPe  NEG')  

                else:         
                    AFG.write('SEQuence:ELEM1:TWAit:SLOPe NEG')  
                    AFG.write('SEQuence:ELEM1:JUMP:SLOPe  POS')  
        ESR(AFG)

        
    elif Mode == 'SEQ':
        AFG.write('SEQuence:NEW')
        AFG.query('*OPC?')
        AFG.write(f'SEQuence:LENGth {len(Sequence_Data)}')
        # need to import the waveforms         
        #print('Sequence Data:')
        #for i in range(len(Sequence_Data)):
        #    print(Sequence_Data[i])

        trans_dict = {}
        catalog = AFG_Get_Catalog(AFG)
        for i in range(len(Sequence_Data)):
            wfm = Sequence_Data[i][5]
            local_key = f'{wfm[0]}_{wfm[1]}'
            if local_key not in trans_dict:
                wfm_name = transfer_wfm(SourceXpress,AFG,wfm,catalog)
                Sequence_Data[i][5] = wfm_name
                trans_dict[local_key] = wfm_name
            else:
                Sequence_Data[i][5] = trans_dict[local_key]
                
            if len(Sequence_Data[i]) == 7:
                wfm = Sequence_Data[i][6]
                local_key = f'{wfm[0]}_{wfm[1]}'
                if local_key not in trans_dict:
                    Sequence_Data[i][6] = transfer_wfm(SourceXpress,AFG,wfm,catalog)
                    Sequence_Data[i][5] = wfm_name
                    trans_dict[local_key] = wfm_name
                else:
                    Sequence_Data[i][6] = trans_dict[local_key]

        slope = SourceXpress.query('TRIGGER:SLOPE? ATRIGGER')
        AFG.write(f'SEQControl:TIMer {Ch1.timer}')

        #print('Sequence Data:')
        #for i in range(len(Sequence_Data)):
        #    print(Sequence_Data[i])
        
        # Build the dumpsterfire of a concatinated command, then <i>send it</i>.    
        # This way I send at most 255 commands to configure the sequncer, instead of >3000, cutting down on processing time.
        # Actual performance gains are untested, however with my experience from scope programming it will be decent.
        #for i in range(len(Sequence_Data)):
        #    print(Sequence_Data[i])

        for i in range(1,len(Sequence_Data)+1):
            message = ''

            # waveform assignements have to go first
            if   Ch1.casset[0] != '' and Ch2.casset[0] == '': 
                message += f'SEQuence:ELEM{i}:WAVeform1 "{Sequence_Data[i-1][5]}"; :' # if its an IQ wfm it will be a list.
            elif Ch1.casset[0] == '' and Ch2.casset[0] != '': 
                message += f'SEQuence:ELEM{i}:WAVeform2 "{Sequence_Data[i-1][5]}"; :'
            else:
                message += f'SEQuence:ELEM{i}:WAVeform1 "{Sequence_Data[i-1][5]}"; :'
                message += f'SEQuence:ELEM{i}:WAVeform2 "{Sequence_Data[i-1][6]}"; :'


            # Handle Wait Event conditions
            if Sequence_Data[i-1][0] == 'ATR': # A Trigger, need slopes.
                message += f'SEQuence:ELEM{i}:TWAit:STATe 1; :SEQuence:ELEM{i}:TWAit:EVENt EXT; :SEQuence:ELEM{i}:TWAit:SLOPe {slope}; :'
            elif Sequence_Data[i-1][0] == 'ITR': # Internal Trigger
                message += f'SEQuence:ELEM{i}:TWAit:STATe 1; :SEQuence:ELEM{i}:TWAit:EVENt TIMer; :'
            elif Sequence_Data[i-1][0] == 'MAN': # B Trigger, set to manual
                message += f'SEQuence:ELEM{i}:TWAit:STATe 1; :SEQuence:ELEM{i}:TWAit:EVENt MANual; :'

            # Handle Repeat count
            if Sequence_Data[i-1][1] == 'ONCE':
                message += f'SEQuence:ELEM{i}:LOOP:COUNt 1; :'
            elif Sequence_Data[i-1][1] == 'INF': 
                message += f'SEQuence:ELEM{i}:LOOP:INFinite 1; :'
            else: 
                message += f'SEQuence:ELEM{i}:LOOP:COUNt {int(Sequence_Data[i-1][1])}; :'

            # Event input  
            if Sequence_Data[i-1][2] == 'ATR':
                message += f'SEQuence:ELEM{i}:JUMP:EVENt EXT; :SEQuence:ELEM{i}:JUMP:SLOPe {slope}; :'
            elif Sequence_Data[i-1][2] == 'ITR':
                message += f'SEQuence:ELEM{i}:JUMP:EVENt TIMer; :'
            elif Sequence_Data[i-1][2] == 'MAN':
                message += f'SEQuence:ELEM{i}:JUMP:EVENt MAN; :'
            
            # Event jump to
            if   Sequence_Data[i-1][3] == 'NEXT':
                message += f'SEQuence:ELEM{i}:JTARget:TYPE NEXT'
            elif Sequence_Data[i-1][3] == 'FIRS':
                message += f'SEQuence:ELEM{i}:JTARget:TYPE INDex; :SEQuence:ELEM{i}:JTARget:INDex 1'
            elif Sequence_Data[i-1][3] == 'LAST':
                message += f'SEQuence:ELEM{i}:JTARget:TYPE INDex; :SEQuence:ELEM{i}:JTARget:INDex {len(Sequence_Data)}'
            else: message += f'SEQuence:ELEM{i}:JTARget:TYPE INDex; :SEQuence:ELEM{i}:JTARget:INDex {int(Sequence_Data[i-1][3])}'
            
            # Go TO
            if   Sequence_Data[i-1][4] == 'NEXT':
                # No-Op since there is no need for setting the goto control, will default to Next if not specified.
                #message += f'; :SEQuence:ELEM{i}:GOTO:STATe 1; :SEQuence:ELM[i]:GOTO:INDEX {int(Sequence_Data[i-1][4])+1}'
                pass
            elif Sequence_Data[i-1][4] == 'FIRS':
                message += f'; :SEQuence:ELEM{i}:GOTO:STATe 1; :SEQuence:ELEM{i}:GOTO:INDex MINimum'
            elif Sequence_Data[i-1][4] == 'LAST':
                message += f'; :SEQuence:ELEM{i}:GOTO:STATe 1; :SEQuence:ELEM{i}:GOTO:INDex MAXimum'
            else: message += f'; :SEQuence:ELEM{i}:GOTO:STATe 1; :SEQuence:ELEM{i}:GOTO:INDex {int(Sequence_Data[i-1][4])}'

            log.debug(message) # debug
            AFG.write(message)
            AFG.query('*OPC?') #make sure that the command has processed.
            ESR(AFG)
    
    AFG.query('*OPC?') # Wait for system to catch up
    AFG.write(f'SEQControl:SRATe {Ch1.SampleRate}') # Set Sample rate
    
    # Set the amplitudes for both channels.  
    AFG.write(f'SEQControl:SOURce1:SCALe {float(Ch1.amplitude)*50}')
    AFG.write(f'SEQControl:SOURce2:SCALe {float(Ch2.amplitude)*50}')
    AFG.write(f'SEQControl:SOURce1:OFFSet {Ch1.offset}')
    AFG.write(f'SEQControl:SOURce2:OFFSet {Ch2.offset}')

    #AFG_Set_Amplitude(SourceXpress,AFG) #
    #AFG_Set_Relays(SourceXpress,AFG)
    # Set the reference controlls
    AFG_Start_Output(AFG,Ch2.casset[0])

    log.debug(f'Setting Clock Mode to: {Ch1.Clock}')
    AFG.write(f'ROSCillator:SOURce {Ch1.Clock}')
    AFG.query('*OPC?')

    if Ch1.casset[0] != '':AFG.write(f'OUTPut1:STATe 1')
    if Ch2.casset[0] != '':AFG.write(f'OUTPut2:STATe 1')

def AFG_Get_Catalog(instrument):
    instrument.write('MMEMory:CDIRectory "M:/"')
    catalog = instrument.query('MMEMory:CATalog?').replace('"','')
    catalog = catalog.split(',')
    filtered = []
    for i in range(len(catalog)):
        if  catalog[i].startswith('SB_'):
            filtered.append(catalog[i])
    return(filtered)

def AFG_Clean_Up(AFG):
    """
    Querys root DIR within the target AFG31k
    Removes all files with prefix SB_ as they are generated by SourceBridge
    Exists to act as a workaround for being unable to put all SB files within their own directory.
        Would be used to contain the mess and delete everything in the DIR for cleanup.
        Now I have to make my own method of keeping track through connection cycles.
        Far from the worst thing in this codebase.
    """
    start = time.time()
    log.info('Running AFG Cleanup...')
    catalog = AFG_Get_Catalog(AFG)
    #print(catalog)
    for i in range(len(catalog)):
        AFG.write(f'mmemory:delete "{catalog[i]}"')
    AFG.query('*OPC?')
    log.info(f'AFG Cleanup finished, processing time: {round(time.time()-start,3)}')

def AFG_Start_Output(AFG,Ch2):
    # This segement is a worakround for three major issues with the sequencer.
    # Setting back to Basic mode, then to Advanced mode seems to hide the issues...
    #   1. Ch1 and Ch2 on advanced mode become desynced by >8µS when run a second time.
    #   2. Ch2 stops responding to triggers  (very nasty desyncs caused by this)
    #       2.a This technically could be useful... 
    #           If you need to generate a dynamic signal out of Ch1 and static out of Ch2... mix of Advanced/Basic mode essentially.
    #   3. Basic mode leaks when the output is disabled, and the relays are closed.
    # I greatly dislike this, but hey it works right?
    #   Hi past me, you naïve idiot.  
    #       While yes this *technically* does work, its dumb as hell.  Not entirly your fault though.
    #       I have done so much optomization regarding wfm loading that this piece of code is a significant part of the cycle time.
    #       Even when dealing with long wfms.  This process typically takes ~3S to complete. 
    #           2S for delays, and ~1S for general processing.
    #       The optomizations I have done cuts the whole system op time to ~4S under some circumstances.
    #       This bug is now a signficant pain to my existance.
    #   Rest in peace, my hopes and dreams of solving problems.

    # Okay, so hear me out wild idea... since this this impacts if the user is using channel 2...
    #   Just dont do this! Otherwise, you got to since things break horridly due to it. 
    if Ch2 != '':
        #print('Contents found in channel 2')
        AFG.write('SEQControl:STATe 0') 
        long_OPC(AFG)
        AFG.query('*OPC?')
        time.sleep(1)
        AFG.write('SEQControl:STATe 1')
        long_OPC(AFG)
        time.sleep(1) # Not fond of needing to add a static timer... but the opc query doesn't help here and I have to use a static delay.
        log.debug('Another 3 seconds wasted!')

    log.info('Setup Complete, Running Sequencer')
    start = time.time()
    AFG.write('SEQControl:RUN:immediate') 
    long_OPC(AFG,timeout = 60) # Give the AFG 60S to process, if working with long wfms/seqs loadtime is >3S
    log.info(f'Sequencer Running, processing time: {round(time.time()-start,2)}')
    
def AFG_Stop_Output(AFG):
    """
    Stops AFG playback, first opens the output relays to reduce odds any glitches show up.
    Resets the sequencer, and clears all data
    *Used to delete, now doesn't for hashing support
        Deletes all data from SourceBridge on instrument to keep disk useage low.
    Checks ESR to ensure no issues arose.  
    """
    AFG.write('OUTPUT1:STATE 0')
    AFG.write('OUTPUT2:STATE 0')
    AFG.query('*OPC?')
    AFG.write('SEQControl:STOP:IMMediate')
    AFG.write(f'WLISt:WAVeform:DELete ALL')
    AFG.write(f'SEQControl:RESET:IMMediate')
    AFG.query('*OPC?')
    # AFG_Clean_Up(AFG) Removing to support hashing wfms improving load speed
    ESR(AFG)

class AFG_Data:
    # This may be a weird approach, BUT it makes things really easy to program.  
    #  A dictionary of classes containing the VISA connections and supporting info.
    # Dictionary - Contains all the known generators IDs as keys, and their classes as values.
    #       Class - Contains the generators values, config, setup, easily accessable values.
    Error = False
    #inst = None
    Output_State = 0

    def __init__(self,initalization):
        self.Name,self.Output_State = initalization.split(';')
        ID = se.query('*IDN?')
        if 'Virtual' not in ID: # If its Real AWG ignore.
            self.Error  = True
            log.info('Real AWG found, ignoring...')
        else:
            if ' ' in self.Name: # Attempt to split the name into ID and Name
                self.Name,self.Visa_ID = self.Name.rsplit(' ',1) # search for the VISA ID within the name string
                self.Visa_ID = self.Visa_ID.replace('"','')
            else: 
                self.Visa_ID = self.Name
            # After extracting the VISA string, attempt to connect to the generator.  
            # first try as a IP string, then as a direct VISA ID
            # Handles if user wants to use USB/GPIB for a connection.
            # GPIB NOT recommended due to low transfer speeds.  (I also find USB finickey at times.)
            # Transfering 256MPts of data would be PAINFUL over GPIB.
            # Yes this will false positive for any AWG names that have a space in them...
            #   HOWEVER, it will fail after connecting, as the AWG's will reply with an invalid ID.
            #   Could you still break this? Yes... but why? Why would you? This tool exists to help you...
            log.info(f'Attempting to connect to: {self.Visa_ID}')
            try: 
                self.inst = rm.open_resource(f'TCPIP::{self.Visa_ID}::INSTR')
             # if not valid IP address attempt to connect as visa string...
            except Exception as e:
                #print(f'ERROR: {e}')
                try: 
                    self.inst = rm.open_resource(self.Visa_ID) # Send it!
                    log.warn('LAN connections are prefered for SourceBridge')
                except Exception as e:
                    #print(f'ERROR: {e}')
                    # Abort this is scuffed.
                    log.error(f'Unable to connect to: {self.Visa_ID}')
                    self.Error = True
            if not self.Error: # connection was made, inntialize the generator
                self.inst.read_termination = '\n'
                self.inst.write_termination = '\n'
                self.inst.encoding = 'latin_1'
                self.inst.write('*CLS')
                self.inst.IDN = self.inst.query('*IDN?')
                temp = self.inst.IDN.split(',')
                self.inst.Vendor            = temp[0]
                self.inst.ID                = temp[1]
                self.inst.SerialNumber      = temp[2]
                self.inst.FirmwareVersion   = temp[3]
                # Quickly compute a firmware 'int' that reoresents the firmware version.
                self.firmware_id = 0

                if self.inst.ID not in valid_ids:
                    log.info(f'Unsupported device found: {self.inst.ID} not an AFG31k, disconnecting.')
                    self.inst.close()
                    self.Error = True
                else:
                    # Only validate the firmware if its an AFG31k.  I don't like this sloution at all, it feels messy for isolating the firmware version number...
                    #print(self.inst.FirmwareVersion)
                    SCPI, self.firmware = self.inst.FirmwareVersion.split(' ') 
                    self.major, self.normal, self.minor = self.firmware.replace('FV:','').split('.')
                    self.firmware_id = int(self.major) * 10000 + int(self.normal) * 100 + int(self.minor)
                    #print(self.firmware_id)
                    if self.firmware_id < 10605:
                        log.error(f'Connected AFG using unsupported firmware! Found  V{self.inst.FirmwareVersion}, SourceBridge requires >= V1.6.5')
                        print('Ctrl + Click the following link to download the minimum firmware for the AFG31k.')   
                        print('https://www.tek.com/en/search?keywords=AFG31000&facets=_templatename%3dsoftware%26parsedsoftwaretype%3dFirmware&sort=desc\n')
                        self.inst.close()
                        self.Error = True
                    else:
                        log.info(f'Connection successful!  Connected to:') 
                        log.info(self.inst.IDN) 
                        # Changing approach to wfm timestamps.  Since wfms might get reused 
                        #self.inst.last_update = 0 # Sets the last update to 0 EPOCH time, if a loaded wfm is older than that please reconsider your life choices.
                        self.inst.wfm_dict = {}
                        ESR(self.inst)
                        afg_innitalization(self.inst)
                        ESR(self.inst)

class ChannelContents:
    # note any global vars will be stored with CH1
    type = None
    casset = None
    is_marker = False
    trigger = None
    trigger_source = None
    timer = None
    v_offset = 0
    v_scale = 0
    length = 0
    SampleRate = 0

class AFG_Config:
    Max_Sr = 250e6 
    Max_Rl = 16e6
    Max_Steps = 256

class logging():
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'
    
    path = r'C:\Temp\SourceBridge\log.txt'
    debug_enable = False

    def __init__(self):
        if not os.path.isdir(os.path.dirname(self.path)):
            os.mkdir(self.path)

    def log(self, message):
        with open(self.path, 'a') as entry:
            entry.write(f'[{datetime.datetime.now()}] {message}\n')

    def info(self, message):
        print(message)
        self.log(f'INFO: {inspect.stack()[1][3]} - {message}')

    def warn(self, message):
        print(f'{self.WARNING}WARNING:  {message}{self.ENDC}')
        self.log(f'WARNING: {inspect.stack()[1][3]} - {message}')

    def error(self, message):
        print(f'{self.ERROR}ERROR: {message}{self.ENDC}')
        self.log(f'ERROR: {inspect.stack()[1][3]} - {message}')

    def debug(self, message):
        if self.debug_enable:
            message = f'DEBUG: {inspect.stack()[1][3]} - {message}'
            self.log(message)

if __name__ == '__main__':
    log = logging()
    log.info('Starting SourceBridge V1.5! Making connection to SourceXpress')
    print('This software was written by Daniel Schneider: daniel.schneider@tektronix.com')
    rm = pyvisa.ResourceManager()
    se = rm.open_resource('GPIB8::1::INSTR')
    se.read_termination = '\n'
    se.write_termination = '\n'
    se.encoding = 'latin_1'
    se.write('*CLS')
    log.info('SourceXpress connected, monitoring status.')

    AFG_Dict = {} # stores all known Virtual Generators

    while True:
        # wait for the output enable command.
        # yeah Polling sourceXpress ain't great... I dont have a better idea... 
        #   Know how to get SourceXpress to send me a message when something gets updated, because I don't.

        #   *Correction, I have a better idea.  Actually intergrate this into SourceExpress
        #   Instead of relying on a jank as all hell script to do this.  
        # There was also a version of SoruceBridge that didn't poll sourcexpress.
        #   Instead it waited for user input to begin transfer.  
        #   However, I wanted this to be transparent to the user, hence the poling.  
        #   Only show the terminal as an output so they could see what it SB is doing.    
        
        Reply_Str = se.query('CONNectivity:ACTive?; :AWGControl:RSTate?')
        Reply_Name,Reply_State = Reply_Str.split(';')
        Reply_State = int(Reply_State)
        if Reply_Name not in AFG_Dict:  
            # Search the AFG_Dict for keys that match the reply's name.
            # if not found, onboard the potential new generator.  
            log.info('New generator detected, validating...')

            # pregenerate the data for each of the values within the AFG Class
            onboarding = AFG_Data(Reply_Str)

            # Regardless of the validity of the generator, add it to the AFG_Dict
            # However, it will have the .Error = True tag, meaning it is not valid.
            # Prevents us trying to re-onboard every cycle.
            AFG_Dict[Reply_Name] = onboarding
        elif AFG_Dict[Reply_Name].Error == False:
            # Known tag, AND not invalid.
            # Check state, and update the real gen if necessary. Then update the known state.
            if Reply_State == AFG_Dict[Reply_Name].Output_State:
                # if they are equal, sleep a bit (to reduce poling rate) and do nothing.
                time.sleep(.25)
            elif Reply_State == 0:
                # we know they are not equal, and the new state is 0, therefor end playback. 
                log.info('Playback stopped, clearing out AFG.')
                AFG_Stop_Output(AFG_Dict[Reply_Name].inst)
                AFG_Dict[Reply_Name].Output_State = Reply_State
            else:
                # we know they are not equal, and the new state is playing.  Therefore begin playback
                log.info('Beginning Transfer')
                timer_start = time.time()
                system_config = ErrorChecking(se,AFG_Dict[Reply_Name].inst)
                if system_config != 0: 
                    #input('Test input, please validate:')
                    AFG_Stop_Output(AFG_Dict[Reply_Name].inst)
                    Transfer_Setup(se,AFG_Dict[Reply_Name].inst,system_config) # only execute if config is valid.
                    ESR(AFG_Dict[Reply_Name].inst)
                    AFG_Dict[Reply_Name].Output_State = Reply_State # save the new state
                    AFG_Dict[Reply_Name].inst.last_update = time.time() # Save the timestamp
                    log.info(f'Beginning playback, total processing time: {round(time.time()-timer_start,2)}s')

                else: # if error occured during setup conversion, stop the playback on 'SourceXpress side' 
                    se.write('AWGCONTROL:STOP:IMMEDIATE')
                    se.query('*OPC?')
                    time.sleep(.25)
            # if its a known tag and invalid, just do nothing.  

    # entirely redundant as at no point will this code execute...
    se.close()
    afg.close()