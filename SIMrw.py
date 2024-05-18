#!/usr/bin/env python3

import sys
import os
import csv
import argparse
from smartcard.util import toBytes, toASCIIString, padd
from smartcard.System import readers
from smartcard.CardConnectionObserver import ConsoleCardConnectionObserver
from smartcard.Exceptions import NoReadersException, CardConnectionException

#USIM setup

debug = False

def usim(reader_nb, pin=None):
    try:
        # get all the available readers
        r = readers()
        if not r:
            raise NoReadersException("No smart card readers found.")
    except NoReadersException as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        reader = r[reader_nb]
    except IndexError:
        print(f"Error: Reader number {reader_nb} is not available. Please select a valid reader.")
        sys.exit(1)

    print("\nUsing:", reader, "\n")

    try:
        connection = reader.createConnection()
        if debug:
            observer = ConsoleCardConnectionObserver()
            connection.addObserver(observer)
        connection.connect()
    except CardConnectionException as e:
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
        data, sw1, sw2 = connection.transmit(toBytes(GET_RESPONSE) + [sw2])
        if (sw1, sw2) != (0x90, 0x00):
            raise Exception("Error in GET RESPONSE")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    size = data[-1]

    if pin is not None:
        try:
            # Convert PIN to string of ASCII values
            pin_str = str(pin)
            pin_ascii = [ord(c) for c in pin_str]
            # Pad PIN to 8 bytes if it's less than 8 bytes
            pin_padded = padd(pin_ascii, 8)
            # Verify CHV
            VERIFY = "A0 20 00 01 08"
            cmd = toBytes(VERIFY) + pin_padded
            data, sw1, sw2 = connection.transmit(cmd)
            if (sw1, sw2) != (0x90, 0x00):
                raise Exception(f"Wrong PIN!!!\n\nCAUTION: There is no counter programmed!!! You have only 3 tries at all! How many are still left? ;)\n")
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    else:
        print(f"ERROR: No PIN provided, but a PIN is required.\nPlease enter valid PIN with '-p xxxx' and start again.\nAborting operation.\n")
        sys.exit(1)

    return size, connection


#Reading

def decode_record(record):
    X = len(record) - 14
    name = toASCIIString(record[0:X - 1]).replace("ÿ", "").strip(".")
    name = name.replace("{", "ä").replace("[", "Ä").replace("|", "ö").replace("\\", "Ö").replace("~", "ü").replace("^", "Ü").replace("}", "ß")

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
            print("Aborting read operation.")
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

            name, phone = decode_record(data)
            writer.writerow([record_idx, name, phone])
            print(f"\rReading record {record_idx}... ", end='', flush=True)
            read_records += 1

    print(f"READY!\nSuccessfully read {read_records} records and wrote to {csv_filename}.\n")


#Writing

def get_records_from_csv(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.reader(file, delimiter=';')
        records = [(int(row[0]), row[1], row[2]) for row in csv_reader]
    return records

def reverse_digits_in_pairs(phone):
    reversed_phone = ''.join([phone[i:i+2][::-1] for i in range(0, len(phone), 2)])
    return reversed_phone

def encode_gsm_7bit(name):
    gsm_7bit_alphabet = "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
    encoded_name = []

    for char in name:
        if char in gsm_7bit_alphabet:
            encoded_char = gsm_7bit_alphabet.index(char) + 1
            encoded_name.append(encoded_char)
        else:
            encoded_name.append(32)
    return encoded_name

def new_record(index, name, phone, size):
    if not name:
        print(f"Writing record {index} as EMPTY")
        return [0xFF] * size

    name = name[:size-14]
    print(f"Writing record {index}: {name} {phone}")

    if phone.startswith("+"):
        phone = phone[1:]
        phone_prefix = "08 91"
    elif phone.startswith("*") or phone.startswith("#"):
        phone_prefix = "03 FF"
    else:
        phone_prefix = "06 81"

    if len(phone) % 2 != 0:
        phone += "F"

    phone = reverse_digits_in_pairs(phone)
    phone = phone.replace('*', 'A').replace('#', 'B').replace('p', 'C')

    record = padd(encode_gsm_7bit(name), size-14) + padd(toBytes(f"{phone_prefix} {phone.replace(' ', '')}"), 14)
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
    parser = argparse.ArgumentParser(description='Read from or write to a USIM card.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-r', '--read', action='store_true', help='Read from the USIM card')
    group.add_argument('-w', '--write', action='store_true', help='Write to the USIM card')
    parser.add_argument('-p', '--pin', type=int, help='PIN for the USIM card')
    parser.add_argument('csv_file', help='CSV file name for reading or writing')
    parser.add_argument('reader_nb', type=int, nargs='?', default=0, help='Reader number (default: 0)')

    args = parser.parse_args()

    if args.read:
        usim_read(args.reader_nb, args.csv_file, args.pin)
    elif args.write:
        if not os.path.isfile(args.csv_file):
            print(f"\nERROR: The CSV file '{args.csv_file}' doesn't exist. Please check filename/path.\nAborting operation.\n")
            sys.exit(1)
        
        records = get_records_from_csv(args.csv_file)
        written_records = usim_write(args.reader_nb, records, args.pin)
        print(f"\nREADY!\nSuccessfully written {written_records} records to SIM card.\n")
