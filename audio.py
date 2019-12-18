from __future__ import print_function
import mysql.connector
import pyaudio
import wave
import struct
import time
import math
import time
import os
import random
import configparser
import mysql.connector
from datetime import datetime
from mysql.connector import errorcode
from wave import Wave_write

def load_configfile() :
    #
    # Процесс загрузки файла конфигурации
    #
    CONFIG_FILENAME = "audio.cfg"
    print(" -> LOAD CONFIG")
    
    # Загрузка файла конфигурации
    config = configparser.ConfigParser()
    config.read(CONFIG_FILENAME)
    return config
    
def get_config_audio(config) :
    #
    # Формирование аудио-конфигурации 
    # на основе указанных в файле настроек
    #
    try:
        audio_config = {}
        audio_config['Channels'] = int( config['AUDIO'].get('Channels'))
        audio_config['Rate'] = int( config['AUDIO'].get('Rate'))
        audio_config['InputBlockTime'] = float( config['AUDIO'].get('InputBlockTime'))
        audio_config['ChunkSize'] = int( audio_config['Rate'] * audio_config['InputBlockTime'])
        audio_config['SourceName'] = config['AUDIO'].get('SourceName')
        audio_config['Format'] = pyaudio.paInt16
        audio_config['ShortNormalize'] = (1.0/32768.0)
        audio_config['SaveFileInterval'] = int(config['AUDIO'].get('SaveFileInterval'))
        audio_config['SaveFileDirectory'] = config['AUDIO'].get('SaveFileDirectory')
        return audio_config
    except:
        print("    GET AUDIO PART OF CONFIG ERROR")
        return None

def get_config_controldb(config) :
    #
    # Формирование конфигурации подключения к управляющей БД
    # на основе указанных в файле настроек
    #
    try:
        db_config = {}
        db_config['User'] = config['CONTROLMYSQL'].get('User')
        db_config['Password'] = config['CONTROLMYSQL'].get('Password')
        db_config['Host'] = config['CONTROLMYSQL'].get('Host')
        db_config['Database'] = config['CONTROLMYSQL'].get('Database')
        return db_config
    except:
        print("    GET CONTROLDB PART OF CONFIG ERROR")
        return None       
        
def get_config_general(config) :
    #
    # Формирование общесистемной конфигурации 
    # на основе указанных в файле настроек
    #
    try:
        general_config = {}
        general_config['Verbose'] = int( config['GENERAL'].get('Verbose'))
        general_config['ShowDevicesList'] = int( config['GENERAL'].get('ShowDevicesList'))
        return general_config
    except:
        print("    GET GENERAL PART OF CONFIG ERROR")
        return None

def get_db_connection(config, interval) :
    #
    # Иниицализация соединения с управляющей БД
    #
    cnx = None
    print(" -> CONTROLLER DATABASE CONNECTION INITIALIZING")
    while True:
        try:
            print("    TRYING TO CONNECT")
            cnx = mysql.connector.connect(
                user = config['User'],
                password = config['Password'],
                host = config['Host'],
                database = config['Database']
            )
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("    ERROR. ACCESS DENIED")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print("    ERROR. DATABASE NOT FOUND")
            else:
                print(err)
            time.sleep(session_check_time)
            continue
        else:
            break
    return cnx
    
def find_microphone(pyaudio, prefered_device_index = None, attempt = 1) :
    #
    # Функция для поиска микрофона, 
    # с которого будет сниматься звук
    #
    microphone_index = None
    if (attempt == 1) :
        print("    SEARCHING MICROPHONE")

    time.sleep(1)

    attempt = attempt + 1
    if (attempt > 10) :
        print("    CANNOT FIND MICROPHONE")
        return microphone_index
    
    numdevices = p.get_device_count()
    if (int(numdevices) > 0) :
        # Автоматический поиск микрофона
        if prefered_device_index is None :
            print("    CANNOT FIND CONFIG DeviceID - AUTO CHOOSING MICROPHONE")
            
            # Поиск подходящего микрофона
            for i in range (0, numdevices) :
                if p.get_device_info_by_host_api_device_index(0,i).get('maxInputChannels') > 0:
                    print("    MICROPHONE FOUND: " + p.get_device_info_by_host_api_device_index(0,i).get('name'))
                    return i
            print("    CANNOT FIND ANY MICROPHONES")
            
        # Указан целевой номер устройства с микрофоном, но не найдено указанного микрофона
        elif int(prefered_device_index) >= numdevices :
            print("    CANNOT FIND TARGET DeviceID " + str(int(prefered_device_index)) +
                  ". FOUND " + str(int(numdevices)) + " DEVICES")
        # Указан целевой номер устройства и он найден в наборе
        else :
            if p.get_device_info_by_host_api_device_index(0,prefered_device_index).get('maxInputChannels') > 0:
                print("    MICROPHONE FOUND: " + p.get_device_info_by_host_api_device_index(0,prefered_device_index).get('name'))
                return prefered_device_index

    # Рекурсивный поиск 
    return find_microphone(pyaudio, prefered_device_index, attempt)

def show_devices_list(pyaudio) :
    numdevices = p.get_device_count()
    for i in range (0,numdevices):

        if p.get_device_info_by_host_api_device_index(0,i).get('maxInputChannels')>0:
            print ("Input Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0,i).get('name'))
            print(p.get_device_info_by_host_api_device_index(0,i))

        if p.get_device_info_by_host_api_device_index(0,i).get('maxOutputChannels')>0:
            print ("Output Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0,i).get('name'))
            print(p.get_device_info_by_host_api_device_index(0,i))
        
def get_rms( block, audio_config ):
    # RMS amplitude is defined as the square root of the 
    # mean over time of the square of the amplitude.
    # so we need to convert this string of bytes into 
    # a string of 16-bit eamples...

    # we will get one short out for each 
    # two chars in the string.
    count = len(block)/2
    format = "%dh"%(count)
    shorts = struct.unpack( format, block )

    # iterate over the block.
    sum_squares = 0.0
    for sample in shorts:
        # sample is a signed short in +/- 32768. 
        # normalize it to 1.0
        n = sample * audio_config['ShortNormalize']
        sum_squares += n*n

    return math.sqrt( sum_squares / count )

def update_session_id(cursor, active_session_id) :
    cursor.execute(f"SELECT session_id FROM active_session WHERE active_session_id = {active_session_id}")
    record = cursor.fetchone()
    return int( record[0])
    
########################################

# Загрузка конфигурации
config = load_configfile()
audio_config = get_config_audio(config)
general_config = get_config_general(config)
controldb_config = get_config_controldb(config)
if (audio_config is None or general_config is None or controldb_config is None) :
    time.sleep(5)
    exit()

# Подключение к управляющей БД
cnx = get_db_connection(controldb_config, 5)
if (cnx is None) :
    print("    CANNOT CONNECT TO CONTROLLER DATABASE")
    time.sleep(5)
    exit()
cursor = cnx.cursor()

# Получение статуса от управляющей БД
cursor.execute(f"SELECT active_session_id FROM active_session WHERE sourcename = {audio_config['SourceName']}")
record = cursor.fetchone()
active_session_id = int( record[0])

# Отображение таблицы найденных устройств
p = pyaudio.PyAudio()
if (general_config['ShowDevicesList']) :
    print(" -> DEVICES LIST")
    show_devices_list(p)
# Поиск и инициализация микрофона
print(" -> MICROPHONE INITIALIZING")
p = pyaudio.PyAudio()
device_id = int(config['AUDIO'].get('DeviceID'))
prefered_device_index = None if device_id == 0 else device_id
microphone_index = find_microphone(p, prefered_device_index)
if microphone_index is None :
    print("    MICROPHONE NOT FOUND. EXIT AFTER 5 SECONDS...")
    time.sleep(5)
    exit()
print(" -> MICROPHONE FOUND. CONNECTING TO MICROPHONE...")
time.sleep(1)
stream = p.open(
    format=audio_config['Format'],
    channels = audio_config['Channels'],
    rate = audio_config['Rate'],
    input = True,
    input_device_index = microphone_index,
    frames_per_buffer = audio_config['ChunkSize'])
print("    MICROPHONE CONNECTED")

print(" -> STARTING OBSERVATION PROCESS")
# Время в секундах между попытками подключения к БД 
# recommended period is 30..120 seconds
session_check_time = int(config['SESSION'].get('SessionCheckTime'))
cur_time = prev_time = prev_file_save_time = 0
session_id = 0
        
# format for INSERT record
insert_template = ("INSERT INTO records "
              "(session_id, source, rms) "
              "VALUES (%s, %s, %s)")

waveFile = None
while True:

    # Обновление идентификатора сессии
    if cur_time == 0 or cur_time - prev_time >= session_check_time :
        # Добавление чанка
        prev_time = cur_time
        
        
        # Получение текущего статуса от управляюбщей БД
        prev_session_id = session_id
        session_id = update_session_id(cursor, active_session_id)
        cnx.commit()
        
        if (int(prev_session_id) != int(session_id)) :
            # Идентификатор сессии изменился, закрытие текущего файла
            if (isinstance(waveFile, Wave_write)) :
                waveFile.close()
                waveFile = None
                print(f"    CLOSE AUDIOFILE SESSION {prev_session_id}")

        print(f"    UPDATE SESSION. Time={cur_time:.2f}, session_id={session_id}, previous_session_id={prev_session_id}")
    
    if session_id < 0:
        break             
    
    # read data blocks anyway
    # in case of session_id = 0 it preventis filling buffer with junk
    data = stream.read(audio_config['ChunkSize'])
    cur_time += audio_config['InputBlockTime']
    
    if session_id == 0 :
        # Сбор данных приостановлен
        continue
        
    # Создание файла
    if (isinstance(waveFile, Wave_write) == False) :
        if os.path.isdir(audio_config['SaveFileDirectory']) == False :
            os.makedirs(audio_config['SaveFileDirectory'])
        
        # Текущее время
        revision = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = os.path.join(audio_config['SaveFileDirectory'], f"{session_id}_{revision}.wav")
        waveFile = wave.open(filename, 'wb')
        waveFile.setnchannels(audio_config['Channels'])
        waveFile.setsampwidth(p.get_sample_size(audio_config['Format']))
        waveFile.setframerate(audio_config['Rate'])
        print(f"    CREATING WAV FILE {filename}")
            
    
    # Получение данных
    block_rms = get_rms( data, audio_config)
    rms_data = (session_id, audio_config['SourceName'], block_rms)

    # Сохранение данных в файл
    try:
        frames = []
        frames.append(data)
        if (isinstance(waveFile, Wave_write)) :
            if (general_config['Verbose']) :
                print("    SAVE FRAMES TO FILE.")
            waveFile.writeframes(b''.join(frames))
    except :
        print("    ERROR SAVING WAV FILE")
        time.sleep(5)
        break

    # Отправка данных
    try:
        if (general_config['Verbose']) :
            print(f"    SEND DATA. Time={cur_time:.2f}, session_id={session_id}, data={block_rms}")
        cursor.execute(insert_template, rms_data)
        cnx.commit()
    except :
        # Ошибка отправки данных
        print(cursor._last_executed)
        time.sleep(5)
        raise

print(" -> OBSERVATION PROCESS FINISHED")

# stop audio recording
stream.stop_stream()
stream.close()
p.terminate()

# close database connection
cursor.close()
cnx.close()

if (isinstance(waveFile, Wave_write)) :
    waveFile.close()
