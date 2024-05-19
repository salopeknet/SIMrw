# SIMrw
Little tool for reading or writing GSM phonebooks as CSV to/from a USIM card with an PC/SC
compatible reader.

Command line only, tested on macOS & Windows. More to come. Perhaps. :)

### Usage (more description to come):
```
*** SIMrw v0.1.0 by Micha Salopek (based on the work of Ludovic Rousseau) ***
see: https://github.com/salopeknet/SIMrw

usage: simrw.py [-h] (-r | -w) [-p PIN] csv_file [reader_nb]

Read or write GSM phonebooks as CSV to/from a USIM card with an PC/SC
compatible reader.

positional arguments:
  csv_file           CSV file name for reading or writing
  reader_nb          Reader number (default: 0 if omitted)

options:
  -h, --help         show this help message and exit
  -r, --read         Read phonebook from the USIM card and save as CSV
  -w, --write        Write CSV phonebook to the USIM card
  -p PIN, --pin PIN  PIN for the USIM card (default: None if omitted. CAUTION:
                     There is no fail counter yet!)
```

### Format of CSV-file:
Either read ut a SIM phonebook first and have a look at the created CSV-file.
Or start a new one like in this example:
```
1;Name1;+491711234567
2;Name2;01727890123
3;Name3;123456789
...
```
First field/column is the 'index number', second the 'name', third the 'phone number'. 
Max. chars in name is 17 (I think). No header line. Delimiter is ';' 

> [!NOTE]
> The conversion of the GSM 7-bit charset is a pain in the ass and I haven't found a nice solution yet.
> For now in 'name' only ASCII-chars and german "Umlauts" (äöüÄÖÜß) are allowed.
> [!NOTE]
