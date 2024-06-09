# SIMrw
Little tool for reading or writing GSM phonebooks as CSV to/from a USIM card with an PC/SC
compatible reader.

Command line only. More to come. Perhaps. :)

### Usage (more description to come):
```
*** SIMrw vX.X.X by Micha Salopek (based on the work of Ludovic Rousseau) ***
see: https://github.com/salopeknet/SIMrw

usage: SIMrw.py [-h] (-r | -w) [-v] [-p PIN] csv_file [reader_nb]

Read or write GSM phonebooks as CSV to/from a USIM card with an PC/SC compatible reader.

positional arguments:
  csv_file           CSV file name for reading or writing
  reader_nb          Reader number (default: 0 if omitted)

options:
  -h, --help         show this help message and exit
  -r, --read         Read phonebook from the USIM card and save as CSV
  -w, --write        Write CSV phonebook to the USIM card
  -v, --verbose      Show names & numbers during reading/writing
  -p PIN, --pin PIN  PIN for the USIM card (default: None if omitted)
```
> [!NOTE]
> The downloadable executables are tested on Windows 10 and macOS Sonoma.
> If you know how, better use the Python script natively. 

> [!NOTE]
> Some (Windows-) antivirus could really freak out but this is false positive!
If you do not trust you can still use the Python script.

> [!NOTE]
> On macOS you'll have to make the downloaded file executable and run it with [option]+[Right Click]->Run the first time to confirm.<br>
> If you prefer Terminal, type in the folder where you have downloaded SIMrw-macOS to:<br>```xattr -r -d com.apple.quarantine ./SIMrw-macOS | chmod +x ./SIMrw-macOS```.<br>Furthermore if you want to shorten the name type<br>```mv ./SIMrw-macOS ./SIMrw```<br>I think, it should be similar for Linux.


### Format of CSV-file:
Either read out a SIM phonebook first and then edit the created CSV-file.
Please avoid using Excel for CSV-editing, because it does funny things with CSV-data...

Or start a new one like in this example:
```
1;Name1;+491711234567
2;Name2;01727890123
3;Name3;123456789
4;;
5;Name5;987654321
...
```
First field/column is the 'index number', second the 'name', third the 'phone number'. 
Max. chars in name is 18 (I think). No header line. Delimiter is ';'. If you have empty records/lines in your CSV, always keep at least the 'index number' (followed by ';;') as a placeholder.
