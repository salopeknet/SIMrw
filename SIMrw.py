#!/usr/bin/env python3

import sys
import os
import csv
import argparse
from smartcard.util import toBytes, padd
from smartcard.util import __dic_GSM_3_38__ as char_dict
from smartcard.System import readers
from smartcard.CardConnectionObserver import ConsoleCardConnectionObserver
from smartcard.Exceptions import NoReadersException, CardConnectionException

# Version information
version = "0.2.5"

# from https://patorjk.com/software/taag/#p=display&f=Ivrit&t=SIMrw
ascii_logo = """
      ____ ___ __  __               
     / ___|_ _|  \/  |_ ____      __
     \___ \| || |\/| | '__\ \ /\ / /
      ___) | || |  | | |   \ V  V / 
     |____/___|_|  |_|_|    \_/\_/  
                                
"""
message_Start = f"\n{ascii_logo}***** SIMrw v{version} by Micha Salopek *****\n(based on the work of Ludovic Rousseau)\nsee: https://github.com/salopeknet/SIMrw\n"
message_End = f"\n\nProgram exits.\n\nHave a nice day!\n"


#USIM setup

debug = False

def usim(reader_nb, pin=None):
    try:
        # get all the available readers
        r = readers()
        if not r:
            print(f"\nERROR: No smart card readers detected.\nPlease ensure that your reader is properly connected and try again.\n")
            sys.exit(1)
    except NoReadersException as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        reader = r[reader_nb]
    except IndexError:
        print(f"\nERROR: Reader number {reader_nb} is not available.\nPlease select a valid reader.\n")
        sys.exit(1)

    print("Using:", reader, "\n")

    try:
        connection = reader.createConnection()
        if debug:
            observer = ConsoleCardConnectionObserver()
            connection.addObserver(observer)
        connection.connect()
    except CardConnectionException as e:
        print(f"ERROR: Unable to connect to the reader.\nDetails: {e}\nPossible Fix: Try to unplug and replug the reader.\n")
        sys.exit(1)

    SELECT = "A0 A4 00 00 02 "
    GET_RESPONSE = "A0 C0 00 00 "

    try:
        # Select MF
        data, sw1, sw2 = connection.transmit(toBytes(SELECT + "3F 00"))
        if sw1 != 0x9F:
            raise Exception("Error selecting MF")

        # Select DF Telecom
        data, sw1, sw2 = connection.transmit(toBytes(SELECT + "7F 10"))
        if sw1 != 0x9F:
            raise Exception("Error selecting DF Telecom")

        # Select EF ADN
        data, sw1, sw2 = connection.transmit(toBytes(SELECT + "6F 3A"))
        if (sw1, sw2) != (0x9F, 0x0F):
            raise Exception("Error selecting EF ADN")

        # Get Response
        data, sw1, sw2 = connection.transmit(toBytes(GET_RESPONSE) + [sw2])
        if (sw1, sw2) != (0x90, 0x00):
            raise Exception("Error in GET RESPONSE")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    size = data[-1]

#    if pin is not None:
    try:
        # Convert PIN to string of ASCII values
        pin_str = str(pin)
        pin_ascii = [ord(c) for c in pin_str]
        # Pad PIN to 8 bytes if it's less than 8 bytes
        pin_padded = padd(pin_ascii, 8)
        # Verify CHV
        PIN_VERIFY = "A0 20 00 01 08"
        cmd = toBytes(PIN_VERIFY) + pin_padded
        data, sw1, sw2 = connection.transmit(cmd)
    
        if (sw1, sw2) == (0x90, 0x00):
            pass
        elif (sw1, sw2) == (0x98, 0x08):
            if pin is not None:
                print("\n NOTE: PIN was provided, but deactivated on SIM-Card. Continuing.\n\n")
                pass
            pass
        elif (sw1, sw2) == (0x98, 0x40):
            print("\n ERROR: PIN1 is LOCKED! Please unlock first.\n")
            sys.exit(1)
        elif (sw1, sw2) == (0x98, 0x04):
            print("\n ATTENTION: Wrong or missing PIN!!!")
            PIN_CHECK_REMAINING = "00 20 00 01 00"
            cmd = toBytes(PIN_CHECK_REMAINING)
            data, sw1, sw2 = connection.transmit(cmd)
            if sw2 == 0xC0:
                print("\n ERROR: PIN1 is LOCKED. Please unlock first.\n")
            else:
                print(f"\n -> {sw2 & 0x0F} attempt(s) left!\n\n")
            sys.exit(1)
        else:
            raise Exception(f"Unexpected response: sw1={sw1}, sw2={sw2}")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    return size, connection

# Conversion for GSM-7bit
def encode_name(name_str):
    return [char_dict.get(char, ord(char)) for char in name_str]

def decode_name(name_enc):
    decoded_name = ''
    for byte in name_enc:
        decoded_name += next((char for char, value in char_dict.items() if value == byte), chr(byte))
    return decoded_name

#Reading

def decode_record(record):
    X = len(record) - 14

    name_bytes = record[0:X - 1]
    name = decode_name(name_bytes).strip("ÿ")

    tel_size = record[X]
    phone = record[X + 2:X + tel_size + 1]

    decoded = ""
    for n in phone:
        hex = "%02X" % n
        high = hex[0]
        low = hex[1]
        decoded += low + high

    if decoded[-1] == "F":
        decoded = decoded[:-1]

    phone = decoded.strip("F")

    if record[X + 1] == 0x91:
        phone = "+" + phone

    phone = phone.replace('A', '*').replace('B', '#').replace('C', 'p')


    return name, phone

def usim_read(reader_nb, csv_filename, pin):
    if os.path.isfile(csv_filename):
        overwrite = input(f"The CSV file '{csv_filename}' already exists. Do you want to overwrite it? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("\nAborted read operation. Please start again.\n")
            return

    (size, connection) = usim(reader_nb, pin)

    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')

        read_records = 0

        for nbr in range(1, 250):
            header = [0xA0, 0xB2]
            record_idx = nbr
            cmd = header + [record_idx, 0x04, size]
            data, sw1, sw2 = connection.transmit(cmd)
            if (sw1, sw2) != (0x90, 0x00):
                break

            print(f"\rReading record {record_idx}... ", end='', flush=True)

 # Print out the raw record data before decoding
 #           print(f"\rRaw record {record_idx}: {data}")

            if args.readdump:
                hex_data = ' '.join('%02X' % byte for byte in data)
                if args.verbose:
                    print(hex_data)

                writer.writerow([record_idx, hex_data])

            else:
                name, phone = decode_record(data)

                if args.verbose:
                    if not name:
                        print("--EMPTY--")
                    else:
                        print(name, phone)

                writer.writerow([record_idx, name, phone])
            
            read_records += 1

    print(f"READY!\nSuccessfully read {read_records} records and written to {csv_filename}.\n")


#Writing

def get_records_from_csv(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.reader(file, delimiter=';')
        records = [(int(row[0]), row[1], row[2]) for row in csv_reader]
    return records

def filter_phone(phone):
    allowed_chars = set('0123456789+*#p')
    return ''.join([char for char in phone if char in allowed_chars])

    
def reverse_digits_in_pairs(phone):
    reversed_phone = ''.join([phone[i:i+2][::-1] for i in range(0, len(phone), 2)])
    return reversed_phone

def new_record(index, name, phone, size):
    if not name:
        if args.verbose:
            print(f"Writing record {index}... --EMPTY--")
        return [0xFF] * size

    name = name[:size-14]
    phone = filter_phone(phone)
    print(f"\rWriting record {index}... ", end='', flush=True)
    if args.verbose:
        print(name, phone)

    if phone.startswith("+"):
        phone = phone[1:]
        phone_prefix = "08 91"
    elif phone.startswith("*"):
        phone_prefix = "03 FF"
    elif phone.startswith("#"):
        phone_prefix = "04 FF"
    else:
        phone_prefix = "06 81"

    if len(phone) % 2 != 0:
        phone += "F"

    phone = phone.replace('*', 'A').replace('#', 'B').replace('p', 'C')
    phone = reverse_digits_in_pairs(phone)

    record = padd(encode_name(name), size-14) + padd(toBytes(f"{phone_prefix}{phone}"), 14)
    return record


def usim_write(reader_nb, records, pin):
    written_records = 0
    (size, connection) = usim(reader_nb, pin)

    for record_idx, name, phone in records:
        record = new_record(record_idx, name, phone, size)
        header = [0xA0, 0xDC]
        cmd = header + [record_idx, 0x04, size] + record
        data, sw1, sw2 = connection.transmit(cmd)

        if (sw1, sw2) != (0x90, 0x00):
            print(f"Error writing record {record_idx}")
        else:
            written_records += 1

    return written_records

if __name__ == "__main__":

    print(message_Start)

    parser = argparse.ArgumentParser(description='Read or write GSM phonebooks as CSV to/from a USIM card with an PC/SC compatible reader.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-r', '--read', action='store_true', help='Read phonebook from the USIM card and save as CSV')
    group.add_argument('-w', '--write', action='store_true', help='Write CSV phonebook to the USIM card')
    group.add_argument('-rd', '--readdump', action='store_true', help='Read Dump: Write direct APDU responses as HEX-Bytes to CSV')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show names & numbers during reading/writing')
    parser.add_argument('-p', '--pin', type=int, help='PIN for the USIM card (default: None if omitted)', default=None)
    parser.add_argument('csv_file', help='CSV file name for reading or writing')
    parser.add_argument('reader_nb', type=int, nargs='?', default=0, help='Reader number (default: 0 if omitted)')

    args = parser.parse_args()

    if args.read or args.readdump:
        usim_read(args.reader_nb, args.csv_file, args.pin)
    elif args.write:
        if not os.path.isfile(args.csv_file):
            print(f"\nERROR: The CSV file '{args.csv_file}' doesn't exist. Please check filename/path.\nAborting operation.\n")
            sys.exit(1)
        records = get_records_from_csv(args.csv_file)
        written_records = usim_write(args.reader_nb, records, args.pin)
        print(f"READY!\nSuccessfully written {written_records} records to SIM card.\n")
        
