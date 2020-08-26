# vznncv-mbed-greentea

## Overview

The project provides wrapper around `mbed test`, `mbedgt` and `mbedhtrun` commands to run 
[Greentea](https://github.com/ARMmbed/mbed-os-tools) tests with
[custom boards](https://os.mbed.com/blog/entry/Custom-and-community-board-support/)
that don't have DAPLink or compatible firmware interface, but has other interfaces
that can upload a code and connect to board STDIO UART interface.

The wrapper allows to run Greentea tests using user defined copy, reset and detect boards methods.

## Configuration and basic usage

1. Install this project into your python environment (python 3.6 or higher is required). 
   After it `vznncv-mbedgtw` command will appear in your environment.

2. Create a custom executable script/program that implements the following commands:

   - `list` command:
     
     ```
     ./<user_script> list
     ```
     
     This command must find your boards, and print the following json object to standard output:
     
     ```json
     [{
       "target_id": "FFFF00000000000000000000",
       "target_name": "BLACKPILL_F401CC",
       "serial_port": "/dev/ttyUSB0",
       "image_format": "elf",
       "reset_command": false
      }]
     ```
     
     where:

        - target_id - unique target id, that represent hexadecimal number with at least 4 digits.
                      First 4 digits represent unique board id. If you don't know which target id
                      you should return and only one board is connected to your host, you can
                      use arbitrary hardcoded number, for example "FFFF00000000000000000000";
        - target_name - name of you board (i.e. name of you custom board or any board that you want to use);
        - serial_port - path to serial port adapter that is connected to this board. You can use a separate
                        adapter like PL2303 or CH340, but you need to associate it with your board inside script;
        - image_format - desired image format for `flash` command. It may be "bin", "hex" or "elf";
        - reset_command - optional flag that indicates if your script provides `reset` command for this target.
    
     If there are no any connected boards, a script should return an empty list `[]`.
     
   - `flash` command:
      
     ```
      ./<user_script> list --target-id "<target-id>" --image-path "<path_to_image>"
     ```
     
     The command must take specified program image, upload it to board and reset board.
     If flashing fails due some reason, the program should return non-zero code.
     
     Command arguments:
     
       - target_id - target id from `list` command
       - image_path - path to compiled image. The image has a format that is specified by `list` command
       
   - `reset` command:
   
     ```
     ./<user_script> reset --target-id "<target-id>"
     ```
     
     This command must reset specified board. It may be used only if corresponding `reset_command` field
     from `list` command output is set to `true`.
     If resetting fails due some reason, the program should return non-zero code.
     
   Script examples can be found in the `example` folder.
     
3. Configure your project to set target, toolchain and profile:

   ```
   mbed config target BLACKPILL_F401CC
   mbed config toolchain GCC_ARM
   mbed config profile debug
   ```
   
4. Write tests according [greentea layout rules](https://os.mbed.com/docs/mbed-os/v6.2/debug-test/greentea-for-testing-applications.html).

5. Run `vznncv-mbedgtw list-tests` command to find name or your test:

   ```
   $ vznncv-mbedgtw list-tests
   Test Case:
       Name: mbed-os-features-device_key-tests-device_key-functionality
       Path: ./mbed-os/features/device_key/TESTS/device_key/functionality
   Test Case:
       Name: mbed-os-features-frameworks-utest-tests-unit_tests-basic_test
       Path: ./mbed-os/features/frameworks/utest/TESTS/unit_tests/basic_test
   ...
   ```
    
    note: this command represents wrapper around `mbed test --greentea --compile-list` command.
    
6. Run test with `vznncv-mbedgtw run-tests` command:

   ```
   vznncv-mbedgtw run-tests -s "<path_to_user_script>" --tests-by-name "<greentea_test_name>"
   ...
   ```
   
   **Important:** to use your custom firmware uploading script/program, you must specify it
   with `-s` option. Otherwise it will try to use ordinary mbed methods.
   
## Usage

### Run library project test

To run project tests `vznncv-mbedgtw run-tests` command can be used as shown bellow:

```
vznncv-mbedgtw run-tests -s "<path_to_user_script>" --tests-by-name "<greentea_test_name>"
```

but unlike `mbed test --greentead --tests-by-name "<greentea_test_name>"` it ignores
`*_main.cpp` and `main.cpp` files in the project folder during test compilation. 
It prevents necessity of a separate project creation without `main` function.

### Run test inside main project file.

Due better IDE support it's more convenient to write tests inside you `main.cpp`, rather
then in the `TESTS` folder. But in this case greentea cannot use them.

To work around this problem a `vznncv-mbedgtw run-main -s "<path_to_user_script>"` can be used.
It will compile current program and run it as a greentea test.

### Debug test

Do debug test a helper `vznncv-mbedgtw debug-tests` command can be used:

1. Run you test in a debug mode with an IDE.

2. Run the following command:

   ```
   vznncv-mbedgtw debug-tests -s "<path_to_user_script>"
   ```
   
3. Debug your test.
