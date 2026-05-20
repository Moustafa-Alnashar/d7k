#define F_CPU 11059200UL

#include <stdio.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>

#include "adc.h"
#include "uart.h"

#define BUTTON_PIN PB0
#define MIC 0

volatile uint8_t sample_ready = 0;
volatile uint8_t current_raw_sample = 0;
int8_t true_dc_offset = 128; // Set this to your calibrated silent offset

void timer1_init_8khz(void) {
    // Set CTC mode (Clear Timer on Compare Match) via WGM12
    TCCR1B |= (1 << WGM12);
    
    // Set Compare Match Value for 8 kHz spacing at 11.0592 MHz clock (Prescaler = 1)
    // Formula: (11059200 / 8000) - 1 = 1381.4 -> 1381
    OCR1A = 1381;
    
    // Enable Timer 1 Output Compare A Match Interrupt
    TIMSK |= (1 << OCIE1A);
    
    // Start timer with Prescaler = 1 (CS10 bit)
    TCCR1B |= (1 << CS10);
}

ISR(TIMER1_COMPA_vect) {
    current_raw_sample = ADC_Read_H(MIC);
    sample_ready = 1;
}

static FILE uart_str = FDEV_SETUP_STREAM(UART_putChar, UART_getChar, _FDEV_SETUP_RW);

int main(void) {
    UART_Init(115200);
    
    stdin = stdout = &uart_str;
    ADC_Init();
    timer1_init_8khz();
    sei();

//    uint8_t test_buffer[128];
    uint8_t test_buffer[2048];

    
    while (1) {
        
        // 1. Capture exactly 128 raw hardware samples
        for (uint8_t i = 0; i < 2048; i++) {
            while (!sample_ready);
            sample_ready = 0;
            test_buffer[i] = current_raw_sample;
        }

        // 2. Compute ZCR exactly how your pipeline does it
        float last_centered = 0.0f;
        float last_sample = 0.0f;
        uint8_t zero_crossings = 0;

        for (uint8_t i = 0; i < 128; i++) {
            float centered = ((float)test_buffer[i] - (float)true_dc_offset) / 128.0f;
            float sample = centered - 0.95f * last_centered;
            last_centered = centered;

            if (i > 0) {
                if ((sample < 0.0f && last_sample >= 0.0f) || (sample > 0.0f && last_sample <= 0.0f)) {
                    zero_crossings++;
                }
            }
            last_sample = sample;
        }
        float avr_zcr = (float)zero_crossings / 128.0f;

        // 3. Print Header and Raw Data so Python can intercept it
        printf("\n--- START FRAME ---\n");
        printf("AVR_ZCR: %.4f\n", avr_zcr);
        printf("AVR_CROSSINGS: %d\n", zero_crossings);
        printf("RAW_DATA:\n");
        for (uint8_t i = 0; i < 2048; i++) {
            printf("%d\n", test_buffer[i]);
        }
        printf("--- END FRAME ---\n");

        _delay_ms(2000); // Debounce / cooldown
    }
}