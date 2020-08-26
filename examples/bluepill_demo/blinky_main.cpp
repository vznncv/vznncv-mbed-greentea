#include "mbed.h"

// project configuration
#define PROJECT_LED LED1

int main()
{
    const int minor_blink_number = 4 * 2;
    const auto minor_blink_delay = 50ms;
    const auto major_blink_delay = 1000ms;

    DigitalOut led(PROJECT_LED, 1);
    int counter = 0;
    printf("<start>\n");

    while (true) {
        for (int i = 0; i < minor_blink_number; i++) {
            led = !led;
            ThisThread::sleep_for(minor_blink_delay);
        }
        printf("Blinky count: %i\n", counter);
        counter++;
        ThisThread::sleep_for(major_blink_delay);
    }
}
