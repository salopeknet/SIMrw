#!/usr/bin/env python3

import sys
import os
import csv
import argparse
from smartcard.util import toBytes, padd
from smartcard.util import __dic_GSM_3_38__ as char_dict
from smartcard.System import readers
from smartcard.CardConnectionObserver import ConsoleCardConnectionObserver
from smartcard.Exceptions import NoCardException, NoReadersException, CardConnectionException

# Version information
version = "0.3.0"

# from https://patorjk.com/software/taag/#p=display&f=Ivrit&t=SIMrw
ascii_logo = """
      ____ ___ __  __               
     / ___|_ _|  \/  |_ ____      __
     \___ \| || |\/| | '__\ \ /\ / /
      ___) | || |  | | |   \ V  V / 
     |____/___|_|  |_|_|    \_/\_/  
                                
"""
message_Start = f"""

{ascii_logo}
***** SIMrw v{version} by Micha Salopek *****
see: https://github.com/salopeknet/SIMrw

"""
message_End = f"\n\nProgram exits.\n\nHave a nice day!\n"

# USIM setup

debug = True

def usim(reader_nb, pin=None, setpin=''):
    try:
        # Get all the available readers
        r = readers()
        if not r:
            print("\nERROR: No smart card readers detected.\nPlease ensure that your reader is properly connected and try again.\n")
            sys.exit(1)
    except NoReadersException as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        reader = r[reader_nb]
    except IndexError:
        print(f"\nERROR: Reader number {reader_nb} is not available.")
        print("Please select a valid reader.\n")
        sys.exit(1)

    print(f"\nUsing:", reader, "\n")

    connection = None
    try:
        connection = reader.createConnection()
        connection.connect()
    except NoCardException:
        print(f"\nERROR: No USIM card detected in the reader.\nPlease insert a USIM card into the reader properly and try again.\n")
        sys.exit(1)
    except CardConnectionException as e:
        if isinstance(e, NoCardException):
            print(f"\nERROR: No USIM card detected in the reader.\nPlease insert a USIM card into the reader properly and try again.\n")
        else:
            print(f"\nERROR: Unable to connect to the reader.\nDetails: {e}\nPossible Fix: Try to unplug and replug the reader.\n")
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
        data, sw1, sw2 = connection.transmit(toBytes(GET_RESPONSE + "0F"))
        if (sw1, sw2) != (0x90, 0x00):
            raise Exception("Error in GET RESPONSE")

        # Extract file size and record size
        file_size = (data[2] << 8) + data[3]
        record_size = data[14]

        # Calculate the number of records
        num_records = file_size // record_size

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    size = record_size

    if pin is not None:
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
                print("\nPIN accepted.\n")
                pass
            elif (sw1, sw2) == (0x98, 0x08):
                print("\nNOTE: PIN was provided, but disabled on SIM-Card. Continuing.\n")
            elif (sw1, sw2) == (0x98, 0x40):
                print("\nERROR: PIN1 is LOCKED! Please unlock first.\n")
                sys.exit(1)
            elif (sw1, sw2) == (0x98, 0x04):
                print("\nATTENTION: Wrong or missing PIN!!!")
                PIN_CHECK_REMAINING = "00 20 00 01"
                cmd = toBytes(PIN_CHECK_REMAINING)
                data, sw1, sw2 = connection.transmit(cmd)
                if (sw1, sw2) == (0x63, 0xC0):
                    raise Exception("\nERROR: PIN1 is LOCKED. Please unlock first.\n")
                elif sw1 == 0x63:
                    raise Exception(f"\n-> {sw2 & 0x0F} attempt(s) left!\n")
                else:
                    raise Exception(f"Unexpected response: sw1={sw1:02X}, sw2={sw2:02X}")
                    sys.exit(1)


            if args.setpin.lower() == 'off':
                print(f"\rDisabling PIN... ", end='', flush=True)
                DISABLE_PIN = "A0 26 00 01 08"  # Command for disabling PIN
                cmd = toBytes(DISABLE_PIN) + pin_padded
                data, sw1, sw2 = connection.transmit(cmd)
                if (sw1, sw2) == (0x90, 0x00):
                    print(f"PIN disabled now!\n")
                elif (sw1, sw2) == (0x98, 0x08):
                    print(f"PIN was disabled already!\n")
                elif (sw1, sw2) == (0x98, 0x04):
                    print("\nATTENTION: Wrong or missing PIN!!!")
                    PIN_CHECK_REMAINING = "00 20 00 01"
                    cmd = toBytes(PIN_CHECK_REMAINING)
                    data, sw1, sw2 = connection.transmit(cmd)
                    if (sw1, sw2) == (0x63, 0xC0):
                        raise Exception("\nERROR: PIN1 is LOCKED. Please unlock first.\n")
                        sys.exit(1)
                    elif sw1 == 0x63:
                        raise Exception(f"\n-> {sw2 & 0x0F} attempt(s) left!\n")
                        sys.exit(1)
                else:
                    raise Exception(f"Unexpected response: sw1={sw1:02X}, sw2={sw2:02X}")
                    sys.exit(1)


            elif args.setpin.lower() == 'on':
                print(f"\rEnabling PIN... ", end='', flush=True)
                ENABLE_PIN = "A0 28 00 01 08"  # Command for enabling PIN
                cmd = toBytes(ENABLE_PIN) + pin_padded
                data, sw1, sw2 = connection.transmit(cmd)
                if (sw1, sw2) == (0x90, 0x00):
                    print(f"PIN {pin_str} is enabled now!\n")
                elif (sw1, sw2) == (0x98, 0x08):
                    print(f"PIN was enabled already!\n")
                elif (sw1, sw2) == (0x98, 0x04):
                    print("\nATTENTION: Wrong or missing PIN!!!")
                    PIN_CHECK_REMAINING = "00 20 00 01"
                    cmd = toBytes(PIN_CHECK_REMAINING)
                    data, sw1, sw2 = connection.transmit(cmd)
                    if (sw1, sw2) == (0x63, 0xC0):
                        raise Exception("\nERROR: PIN1 is LOCKED. Please unlock first.\n")
                        sys.exit(1)
                    elif sw1 == 0x63:
                        raise Exception(f"\n-> {sw2 & 0x0F} attempt(s) left!\n")
                        sys.exit(1)
                else:
                    raise Exception(f"Unexpected response: sw1={sw1:02X}, sw2={sw2:02X}")
                    sys.exit(1)


            elif args.setpin and args.setpin.isdigit() and 4 <= len(args.setpin) <= 8:
                print(f"\rChanging PIN... ", end='', flush=True)
            
                npin_str = args.setpin
                npin_ascii = [ord(c) for c in npin_str]
                npin_padded = padd(npin_ascii, 8)
            
                CHANGE_PIN = "A0 24 00 01 10"  # Command for changing PIN1
                cmd = toBytes(CHANGE_PIN) + pin_padded + npin_padded
                data, sw1, sw2 = connection.transmit(cmd)
                if (sw1, sw2) == (0x90, 0x00):
                    print(f"PIN was changed to {npin_str}!\n")
                    
                ENABLE_PIN = "A0 28 00 01 08"  # Command for enabling PIN
                cmd = toBytes(ENABLE_PIN) + npin_padded
                data, sw1, sw2 = connection.transmit(cmd)
                if (sw1, sw2) == (0x90, 0x00):
                    print(f"The new PIN is enabled!\n")
                elif (sw1, sw2) == (0x98, 0x08):
                    print(f"The new PIN is also enabled now!\n")
                elif (sw1, sw2) == (0x98, 0x04):
                    print("\nATTENTION: Wrong or missing PIN!!!")
                    PIN_CHECK_REMAINING = "00 20 00 01"
                    cmd = toBytes(PIN_CHECK_REMAINING)
                    data, sw1, sw2 = connection.transmit(cmd)
                    if (sw1, sw2) == (0x63, 0xC0):
                        print("\nERROR: PIN1 is LOCKED. Please unlock first.\n")
                        sys.exit(1)
                    elif sw1 == 0x63:
                        print(f"\n-> {sw2 & 0x0F} attempt(s) left!\n")
                        sys.exit(1)

                else:
                    raise Exception(f"Unexpected response: sw1={sw1:02X}, sw2={sw2:02X}")
                    sys.exit(1)

            else: 
                if args.setpin:
                    print(f"Invalid value for '-sp' / '--setpin'. Possible options are:\n - OFF to disable PIN1\n - ON to enable PIN1\n - The new PIN must be a numeric value between 4 and 8 digits.")


        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)


    return size, connection, num_records

# Conversion for GSM-7bit
def encode_name(name_str):
    return [char_dict.get(char, ord(char)) for char in name_str]

def decode_name(name_enc):
    decoded_name = ''
    for byte in name_enc:
        decoded_name += next((char for char, value in char_dict.items() if value == byte), chr(byte))
    return decoded_name

# Reading

def decode_record(record):
    X = len(record) - 14

    name_bytes = record[0:X - 1]
    name = decode_name(name_bytes).strip("ÿ")

    tel_size = record[X+1]
    phone = record[X + 2:X + tel_size]

    decoded = ""
    for n in phone:
        hex = "%02X" % n
        high = hex[0]
        low = hex[1]
        decoded += low + high

    if decoded[-1] == "F":
        decoded = decoded[:-1]

    phone = decoded.strip("F")

    phone = phone.replace('A', '*').replace('B', '#').replace('C', 'p')

    if record[X + 1] == 0x91:
        # Add '+' as a prefix if international phone number
        if phone and phone[0].isdigit():
            phone = "+" + phone
        # Check if USSD-Code for call divert with international number
        if (phone.startswith("**") and phone[2:3].isdigit() and phone[4] == '*'):
            phone = phone[:5] + "+" + phone[5:]
        # Check if 2-digit-USSD-Code with international number
        elif (phone[0] in "*#" and phone[1:2].isdigit() and phone[3] in "*#"):
            phone = phone[:4] + "+" + phone[4:]
 
    return name, phone

def usim_read(reader_nb, csv_filename, pin, setpin, args):
    if os.path.isfile(csv_filename):
        overwrite = input(f"The CSV file '{csv_filename}' already exists. Do you want to overwrite it? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("\nAborted read operation. Please start again.\n")
            return

    (size, connection, num_records) = usim(reader_nb, pin)
    
    print(f"Opened USIM card with {num_records} availiable phonebook entries.\n")

    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')

        read_records = 0

        for nbr in range(1, num_records+1):
            read_record = [0xA0, 0xB2]
            record_idx = nbr
            cmd = read_record + [record_idx, 0x04, size]
            data, sw1, sw2 = connection.transmit(cmd)
            if (sw1, sw2) != (0x90, 0x00):
                break

            print(f"\rReading record {record_idx}... ", end='', flush=True)

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

    print(f"READY!\nSuccessfully read {read_records} records and written to '{csv_filename}'.\n")


# Writing

def get_records_from_csv(file_path, args):
    with open(file_path, mode='r') as file:
        csv_reader = csv.reader(file, delimiter=';')
        if args.writedump:
            records = [(int(row[0]), row[1]) for row in csv_reader]
        else:
            records = [(int(row[0]), row[1], row[2]) for row in csv_reader]
    return records

def filter_phone(phone):
    allowed_chars = set('0123456789+*#p')
    return ''.join([char for char in phone if char in allowed_chars])

def reverse_digits_in_pairs(phone):
    reversed_phone = ''.join([phone[i:i+2][::-1] for i in range(0, len(phone), 2)])
    return reversed_phone

def new_record(index, name, phone, size, args):
    if not name:
        if args.verbose:
            print(f"--EMPTY--")
        return [0xFF] * size

    name = name[:size-14]

    if not phone:
        phone_data = [0xFF] * 14
        record = padd(encode_name(name), size-14) + phone_data
        return record

    phone = filter_phone(phone)

    if args.verbose:
        print(name, phone)

    #check for international number
    if "+" in phone:
        phone = phone.replace('+', '')
        phone_prefix = "91"
    #check for plain USSD-code
    elif (phone.startswith(('*', '**', '#', '##', '*#')) and phone.endswith(('*', '#')) and phone.strip('*#').isdigit()):
        phone_prefix = "FF"
    #else national number
    else:
        phone_prefix = "81"

    if len(phone) % 2 != 0:
        phone += "F"

    phone = phone.replace('*', 'A').replace('#', 'B').replace('p', 'C')
    phone = reverse_digits_in_pairs(phone)

    phone_length = (len(phone) // 2) + 1
    phone_data = padd(toBytes(f"{phone_length:02X}{phone_prefix}{phone}"), 14)

    record = padd(encode_name(name), size-14) + phone_data
    return record

def usim_write(reader_nb, records, pin, setpin, args):
    written_records = 0
    (size, connection, num_records) = usim(reader_nb, pin)

    print(f"Opened USIM card with {num_records} available phonebook entries.\n")

    num_records_to_write = len(records)
    
    if num_records_to_write < num_records:
        fill_empty = input(f"\nATTENTION: The number of entries in the CSV ({num_records_to_write}) is less than the phonebook size ({num_records}) on USIM card!\n\nDo you want to fill the remaining entries with empty records (and overwrite existing records on card)? (y/n): ").strip().lower()
        if fill_empty == 'y':
            for i in range(num_records_to_write + 1, num_records + 1):
                if args.write:
                    records.append((i, "", ""))
                if args.writedump:
                    records.append((i, ('FF ' * size).strip()))

    if num_records_to_write > num_records:
        print(f"\nATTENTION: The number of entries in the CSV ({num_records_to_write}) is more than the phonebook size ({num_records}) of USIM card!\n\nPlease edit the CSV-File down to max. {num_records} entries and start over!\nAborting operation.\n\n")
        sys.exit(1)

    if args.write:
        for record_idx, name, phone in records:
            print(f"\rWriting record {record_idx}... ", end='', flush=True)

            record = new_record(record_idx, name, phone, size, args)
            write_record = [0xA0, 0xDC]
            cmd = write_record + [record_idx, 0x04, size] + record
            data, sw1, sw2 = connection.transmit(cmd)

            if (sw1, sw2) != (0x90, 0x00):
                print(f"Error writing record {record_idx}")
            else:
                written_records += 1

    elif args.writedump:
        for record_idx, hex_bytes in records:
            print(f"\rWriting record {record_idx}... ", end='', flush=True)

            if args.verbose:
                print(hex_bytes)

                bytes_data = bytes.fromhex(hex_bytes)

                write_record = [0xA0, 0xDC]
                cmd = write_record + [record_idx, 0x04, size] + list(bytes_data)
                data, sw1, sw2 = connection.transmit(cmd)

                if (sw1, sw2) != (0x90, 0x00):
                    print(f"Error writing record {record_idx}")
                else:
                    written_records += 1

    print(f"READY!\nSuccessfully written {written_records} records to SIM card.\n")

    

if __name__ == "__main__":
    print(message_Start)
    print(f"Starting application...\n")

    parser = argparse.ArgumentParser(description='Read or write GSM phonebooks as CSV to/from a USIM card with a PC/SC compatible reader.')
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-r', '--read', action='store_true', help='Read phonebook from the USIM card and save as CSV')
    group.add_argument('-w', '--write', action='store_true', help='Write CSV phonebook to the USIM card')
    group.add_argument('-rd', '--readdump', action='store_true', help='Write direct APDU responses (dump) as HEX-Bytes to CSV (bytewise backup)')
    group.add_argument('-wd', '--writedump', action='store_true', help='Write Dump: Write HEX-Bytes from (dumped) CSV to USIM card')

    parser.add_argument('-v', '--verbose', action='store_true', help='Show names & numbers during reading/writing')
    parser.add_argument('-p', '--pin', type=int, help='PIN1 for the USIM card (default: None if omitted, but needed for --setpin / -sp !!)', default=None)
    parser.add_argument('-sp', '--setpin', type=str, help='Can be ON/OFF or [NEW_PIN] (4 to 8 digits).\nCan be used standalone or in combination with read/write process.', default='')
    parser.add_argument('csv_file', nargs='?', default='', help='CSV file name for reading or writing')
    parser.add_argument('reader_nb', type=int, nargs='?', default=0, help='Reader number (default: 0 if omitted)')

    if len(sys.argv) == 1:
        parser.print_help()
        print(f"\n\n!!! This is a command-line only tool !!!\n\nYou have to pass some arguments (see above)... :)\n\nFor example type 'SIMrw -r phonebook.csv' to read a phonebook from SIM-card to save a csv-file.\n\nPress [ENTER] to exit and try again.")
        input()
        sys.exit(0)

    args = parser.parse_args()

    if args.setpin:
        if not args.pin:
            print(f"\nERROR: No PIN provided. Please provide valid PIN.\nAborting operation.\n\n")
            sys.exit(1)
        if not (args.read or args.readdump or args.write or args.writedump):
            usim(args.reader_nb, args.pin, args.setpin)

    if args.read or args.readdump:
        if args.csv_file == '':
            print(f"\nERROR: No filename for CSV provided. Please provide filename/path.\nAborting operation.\n\n")
            sys.exit(1)
        usim_read(args.reader_nb, args.csv_file, args.pin, args.setpin, args)
    
    if args.writedump or args.write:
        if not os.path.isfile(args.csv_file):
            print(f"\nERROR: The CSV file '{args.csv_file}' doesn't exist. Please check filename/path.\nAborting operation.\n\n")
            sys.exit(1)
        records = get_records_from_csv(args.csv_file, args)
        if args.write:
            usim_write(args.reader_nb, [(idx, name, phone) for idx, name, phone in records], args.pin, args.setpin, args)
        elif args.writedump:
            usim_write(args.reader_nb, [(idx, data) for idx, data in records], args.pin, args.setpin, args)

    print(message_End)
