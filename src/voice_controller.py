import argparse
import os
import queue
import sounddevice as sd
import vosk
import sys
import math
from word2number import w2n

q = queue.Queue()


# Input -> Output = '{\n  "text" : "command"\n}' -> 'command'
def result_to_command(result):
    # result = '{\n  "text" : "command"\n}'
    result = result.split("\n")[1]
    # result = '  "text" : "command"'
    result = result.split('"')[3]
    # result = command
    return result


# correct command for miss-interpreted homophones
def correct_command_str(command):
    command = command.replace("to ", "two ")
    command = command.replace("too ", "two ")
    command = command.replace("for ", "four ")
    command = command.replace("the ", "")
    command = command.replace("a ", "")
    command = command.replace("feed", "feet")

    return command


# Processes command and sends it to rover
def handel_command(command):

    # print input string
    print("command:", command)

    # correct command for confusion of 'to' and 'two', etc.
    if correct_command_str(command) != command:
        command = correct_command_str(command)
        print("command corrected to '%s'" % command)

    # read integer argument from command (if supplied)
    x = 0
    try:
        x = w2n.word_to_num(command)
    except ValueError:
        pass


    # adjust for different units (yes, you can turn 1 meter (: )
    if "feet" in command:
        x = 12 * x

    """
    Execute commands
    """
    # halt all motion
    if "stop" in command:
        print("stopping")

    # drivetrain commands
    elif "forward" in command:
        print("moving forward %d inches" % x)

    elif "backward" in command:
        print("moving backward %d inches" % x)

    elif "right" in command:
        print("turning right %d degrees" % x)

    elif "left" in command:
        print("turning left %d degrees" % x)

    # stabilizer commands
    elif "lift" in command:
        print("lifting %d degrees" % x)

    elif "lower" in command:
        print("lowering %d degrees" % x)

    # claw commands
    elif "close" in command:
        print("closing claw %d degrees" % x)
    elif "open" in command:
        print("opening claw %d degrees" % x)


def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    '-l', '--list-devices', action='store_true',
    help='show list of audio devices and exit')
args, remaining = parser.parse_known_args()

if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[parser])

parser.add_argument('-f', '--filename', type=str, metavar='FILENAME', help='audio file to store recording to')
parser.add_argument('-m', '--model', type=str, metavar='MODEL_PATH', help='Path to the model')
parser.add_argument('-d', '--device', type=int_or_str, help='input device (numeric ID or substring)')
parser.add_argument('-r', '--samplerate', type=int, help='sampling rate')
args = parser.parse_args(remaining)

try:
    if args.model is None:
        args.model = "vosk-model-small-en-us-0.15"
    if not os.path.exists(args.model):
        print("Please download a model for your language from https://alphacephei.com/vosk/models")
        print("and unpack as 'model' in the current folder.")
        parser.exit(0)
    if args.samplerate is None:
        device_info = sd.query_devices(args.device, 'input')
        # soundfile expects an int, sounddevice provides a float:
        args.samplerate = int(device_info['default_samplerate'])

    model = vosk.Model(args.model)

    if args.filename:
        dump_fn = open(args.filename, "wb")
    else:
        dump_fn = None

    with sd.RawInputStream(samplerate=args.samplerate, blocksize=8000, device=args.device, dtype='int16',
                           channels=1, callback=callback):
            print('#' * 80)
            print('Press Ctrl+C to stop the recording')
            print('#' * 80)

            rec = vosk.KaldiRecognizer(model, args.samplerate)

            last_partial_result = ""
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    command = result_to_command(rec.Result())  # turn recognizer output into usable string
                    handel_command(command)  # decode string into command for robot

                elif rec.PartialResult() != last_partial_result:
                    # print("partial:", result_to_command(rec.PartialResult()))
                    last_partial_result = rec.PartialResult()
                if dump_fn is not None:
                    dump_fn.write(data)

except KeyboardInterrupt:
    print('\nDone')
    parser.exit(0)
except Exception as e:
    parser.exit(type(e).__name__ + ': ' + str(e))
