###########################################################################
##                                                                       ##
##                  Language Technologies Institute                      ##
##                     Carnegie Mellon University                        ##
##                         Copyright (c) 2011                            ##
##                        All Rights Reserved.                           ##
##                                                                       ##
##  Permission is hereby granted, free of charge, to use and distribute  ##
##  this software and its documentation without restriction, including   ##
##  without limitation the rights to use, copy, modify, merge, publish,  ##
##  distribute, sublicense, and/or sell copies of this work, and to      ##
##  permit persons to whom this work is furnished to do so, subject to   ##
##  the following conditions:                                            ##
##   1. The code must retain the above copyright notice, this list of    ##
##      conditions and the following disclaimer.                         ##
##   2. Any modifications must be clearly marked as such.                ##
##   3. Original authors' names are not deleted.                         ##
##   4. The authors' names are not used to endorse or promote products   ##
##      derived from this software without specific prior written        ##
##      permission.                                                      ##
##                                                                       ##
##  CARNEGIE MELLON UNIVERSITY AND THE CONTRIBUTORS TO THIS WORK         ##
##  DISCLAIM ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING      ##
##  ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN NO EVENT   ##
##  SHALL CARNEGIE MELLON UNIVERSITY NOR THE CONTRIBUTORS BE LIABLE      ##
##  FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES    ##
##  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN   ##
##  AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,          ##
##  ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF       ##
##  THIS SOFTWARE.                                                       ##
##                                                                       ##
###########################################################################
##                                                                       ##
##  Author: Alok Parlikar (aup@cs.cmu.edu)                               ##
##  Date  : November 2011                                                ##
###########################################################################
"""
Use Google Speech Recognition Service to convert speech into text
"""

import json
import sys
import time
import os

from subprocess import call as execute
from tempfile import NamedTemporaryFile
from urllib2 import urlopen, Request

sox_binary = "/usr/bin/sox"


def _convert_unheadered_wavefile_to_flac(inputfilename,
                                         outputfilename,
                                         input_sample_rate=16000,
                                         input_sample_type='signed',
                                         input_sample_bitsize=16):
    """
    Converts raw unheadered samples into flac data
    Arguments:
    - `inputfilename`: Read RAW wave data from this file
    - `outputfilename`: Save FLAC data to this file (overwrite existing file)
                        FLAC will be saved at 16k samples/sec
    - `input_sample_rate`: Sampling rate of RAW input data
    - `input_sample_type`: Type of RAW sample values (signed/unsigned)
    - `input_sample_bitsize`: Size of each input sample in bits
    """

    conversion_command = map(str, [sox_binary,
                                   "-t", "raw",
                                   "-r", input_sample_rate,
                                   "-e", input_sample_type,
                                   "-b", input_sample_bitsize,
                                   inputfilename,
                                   "-t", "flac",
                                   "-r", "16k",
                                   outputfilename])
    conversion_success = True
    retcode = 0
    try:
        retcode = execute(conversion_command)
    except Exception as e:
        print >> sys.stderr, "Error: %s" % e
        conversion_success = False

    if retcode != 0:
        conversion_success = False

    return conversion_success


def _convert_headered_wavefile_to_flac(inputfilename,
                                       outputfilename):
    """
    Converts a wavefile into flac data file
    Arguments:
    - `inputfilename`: Read Headered wave data from this file
    - `outputfilename`: Save FLAC data to this file (overwrite existing file)
                        FLAC will be saved at 16k samples/sec
    """

    conversion_command = [sox_binary,
                          inputfilename,
                          "-t", "flac",
                          "-r", "16k",
                          outputfilename]
    conversion_success = True
    retcode = 0
    try:
        retcode = execute(conversion_command)
    except Exception as e:
        print >> sys.stderr, "Error: %s" % e
        conversion_success = False

    if retcode != 0:
        conversion_success = False

    return conversion_success


def _run_google_asr(flac_data, max_results=1, profanity_filter=True):
    """
    Send flac data to Google Web Service and return recognition results

    Arguments:
    - `flac_data`: Complete flac data of the audio to be recognized
    - `max_results`: Maximum number of alternative recognition hypotheses
                     to retrieve
    - `profanity_filter`: True/False whether to mask bad words

    Output: List of Hypotheses dictionaries:
            [{'utterance': 'hypothesis',
              'confidence': 0.9},
            ...
            ]
    """

    http_headers = {'Content-Type': 'audio/x-flac; rate=16000'}
    http_url = "http://www.google.com/speech-api/v1/recognize?xjerr=1"

    http_url = '&'.join([http_url,
                         "client=py_google_asr",
                         "lang=cs"])

    if max_results > 1:
        http_url = '&'.join([http_url, "maxresults=%d" % max_results])

    if profanity_filter:
        http_url = '&'.join([http_url, "pfilter=2"])
    else:
        http_url = '&'.join([http_url, "pfilter=0"])

    http_request = Request(http_url, flac_data, http_headers)

    asr_attempt = 0

    results = []

    # If Google returns an error, we try again, upto 3 times.
    while asr_attempt < 3:
        asr_error_occurred = False
        asr_attempt += 1
        try:
            http_response = urlopen(http_request)
        except:
            # Sleep and retry.
            print >> sys.stderr, "HTTP Error. Sleeping and Retrying."
            time.sleep(1)
            continue

        http_result = json.loads(http_response.read().decode('utf-8'))
        status = -1

        try:
            status = http_result['status']
        except:
            asr_error_occurred = True

        if status == 0:
            try:
                results = http_result['hypotheses']
            except:
                asr_error_occurred = True
        else:
            asr_error_occurred = True

        if not asr_error_occurred:
            break

    return results


def decode_wavefile(inputfilename,
                    wavefile_has_header=True,
                    unheadered_sample_rate=16000,
                    unheadered_sample_type='signed',
                    unheadered_sample_bitsize=16,
                    max_results=1,
                    profanity_filter=True):
    """
    Runs Recognition on waveform speech data
    Arguments:
    - `inputfilename`: Read wave data from this file
    - `wavefile_has_header`: True/False depending on if RAW file is used
    - `unheadered_sample_rate`: Sampling rate if using unheadered file
    - `unheadered_sample_type`: signed/unsigned if using unheadered file
    - `unheadered_sample_bitsize`: Size of each input sample in bits
                                   (If using unheadered file)
    - `max_results`: Maximum number of ASR hypotheses to retrieve
    - `profanity_filter`: True/False whether to mask bad words

    Output: List of Hypotheses dictionaries:
            [{'utterance': 'hypothesis',
              'confidence': 0.9},
            ...
            ]
            Note: Google does not seem to return confidence values
                  for all hypothesis.
    """

    tmp_flac_file = NamedTemporaryFile()

    if wavefile_has_header:
        valid_flac_file = _convert_headered_wavefile_to_flac(inputfilename,
                                                            tmp_flac_file.name)
    else:
        valid_flac_file = _convert_unheadered_wavefile_to_flac(
            inputfilename,
            tmp_flac_file.name,
            unheadered_sample_rate,
            unheadered_sample_type,
            unheadered_sample_bitsize)

    if not valid_flac_file:
        print >> sys.stderr, "Could not decode %s" % inputfilename
        return []

    tmp_flac_file.seek(0)
    flac_data = tmp_flac_file.read()
    tmp_flac_file.close()

    if not flac_data:
        # Don't bother recognizing empty file
        print >> sys.stderr, "Could not decode %s. FLAC file was empty." % inputfilename
        return []

    return _run_google_asr(flac_data, max_results, profanity_filter)


if __name__ == '__main__':
    # Run decoding on a wavefile specified on the commandline

    if len(sys.argv) != 2:
        print("Usage: %s short_speech.wav" % sys.argv[0])
        sys.exit(-1)

    wavefilename = sys.argv[1]
    asr_output = decode_wavefile(wavefilename)
    if not asr_output:
        print >> sys.stderr, "ASR Failed to run on %s" % wavefilename
    else:
        hypothesis = asr_output[0]['utterance']
        print(hypothesis)
