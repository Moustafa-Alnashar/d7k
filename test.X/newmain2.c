#define F_CPU 11059200UL

#include <stdio.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>

#include "adc.h"
#include "uart.h"

#define MIC 0

// Total continuous samples to stream per batch sequence (~0.64 seconds)
#define TOTAL_SAMPLES ((uint16_t)5120)

volatile uint8_t sample_ready = 0;
volatile uint8_t current_raw_sample = 0;
int8_t true_dc_offset = 128; 

void timer1_init_8khz(void) {
    TCCR1B |= (1 << WGM12); // CTC mode
    OCR1A = 1381;           // 8 kHz tick rate
    TIMSK |= (1 << OCIE1A); // Enable interrupt
    TCCR1B |= (1 << CS10);  // Prescaler = 1
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

    while (1) {
        uint32_t total_zero_crossings = 0;
        float last_centered = 0.0f;
        float last_sample = 0.0f;

        // 1. Tell Python the batch has started
        printf("\n--- START BATCH ---\n");
        printf("TOTAL_SAMPLES: %u\n", TOTAL_SAMPLES);

        // 2. Pure Streaming: Zero Arrays, Zero Memory Footprint
        for (uint16_t i = 0; i < TOTAL_SAMPLES; i++) {
            // Wait precisely for the 8kHz clock hardware edge
            while (!sample_ready);
            sample_ready = 0;
            
            uint8_t raw = current_raw_sample;

            // Compute DSP math on-the-fly
            float centered = ((float)raw - (float)true_dc_offset) / 128.0f;
            float sample = centered - 0.95f * last_centered; // Pre-emphasis
            last_centered = centered;

            if (i > 0) {
                if ((sample < 0.0f && last_sample >= 0.0f) || (sample > 0.0f && last_sample <= 0.0f)) {
                    total_zero_crossings++;
                }
            }
            last_sample = sample;

            // Stream the single byte onto the serial wire instantly.
            // This takes ~86.8us, returning control before the next 125us interrupt!
            UART_put_uint8_t(raw); 
        }

        // 3. Output trailing pipeline processing metrics
        float avr_zcr = (float)total_zero_crossings / (float)TOTAL_SAMPLES;
        printf("\nAVR_CROSSINGS: %lu\n", total_zero_crossings);
        printf("AVR_ZCR: %.4f\n", avr_zcr);
        printf("--- END BATCH ---\n");

        _delay_ms(3000); // Peace window for desktop processing loops
    }
}