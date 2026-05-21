#define F_CPU 11059200UL
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdlib.h>
#include <stdio.h>
#include "uart.h"

volatile uint8_t sample_ready = 0;
volatile uint8_t current_raw_sample = 0;
uint8_t true_dc_offset = 127;
#define N_FEATURES 10 


void capture_audio_features(float* zcr_out, float* ste_out) {
    for (uint8_t frame = 0; frame < N_FEATURES; frame++) {
        float energy = 0.0f;
        uint8_t zero_crossings = 0;
        float last_centered = 0.0f;
        float last_sample = 0.0f;


        for (uint8_t i = 0; i < 128; i++) {
            // Wait for the hardware timer to tick
            while (!sample_ready);
            sample_ready = 0; // Clear flag

            uint8_t reading = current_raw_sample;
            UART_put_uint8_t(reading);
            
            float centered = ((float)reading - (float)true_dc_offset) / 128.0f;

            float sample = centered - .95f * last_centered;
            energy += sample * sample;

            if (i > 0) {
                int current_sign = (sample < 0.0f);
                int last_sign = (last_sample < 0.0f);
                
                if (current_sign != last_sign) {
                    zero_crossings++;
                }
            }
            last_sample = sample;
            last_centered = centered;
        }
        
        zcr_out[frame] = (float)zero_crossings / 128.0f;
        ste_out[frame] = energy / 128;//2097152.0f; // 128(average) * 128 * 128(normalization)
    }
}

void UART_send_string(const char* str) {
    while (*str) {
        UART_put_uint8_t(*str++);
    }
}

// ---------------------------------------------------------
// ADD THIS: A mock hardware interrupt to test the UART stream
// (Replace this with your real ADC interrupt later)
// ---------------------------------------------------------
ISR(TIMER0_COMP_vect) {
    // Generate a dummy audio byte between 100 and 150
    current_raw_sample = 100 + (rand() % 50); 
    sample_ready = 1; // This breaks the while(!sample_ready) loop!
}

void Timer0_init_mock(void) {
    TCCR0 = (1<<WGM01) | (1<<CS01) | (1<<CS00); // CTC mode, prescaler 64
    OCR0 = 30; // Approx 8kHz sample rate at 16MHz clock
    TIMSK |= (1<<OCIE0); // Enable Timer 0 compare interrupt
}
// ---------------------------------------------------------

int main(void) {
    // Initialize UART at 115200 baud
    unsigned int ubrr = F_CPU/16/115200-1;
    UBRRH = (unsigned char)(ubrr>>8);
    UBRRL = (unsigned char)ubrr;
    UCSRB = (1<<TXEN); 
    UCSRC = (1<<URSEL)|(3<<UCSZ0);

    // CALL YOUR INTERRUPT INITIALIZATION HERE
    Timer0_init_mock(); 
    
    sei(); // Enable global interrupts so the timer can run

    float zcr_out[N_FEATURES] = {0};
    float ste_out[N_FEATURES] = {0};

    // Send a startup message so you know the board is alive
    UART_send_string("ATmega32A Booted. Starting capture...\n");

    while (1) {
        capture_audio_features(zcr_out, ste_out);

        UART_send_string("\n---RESULTS---\n");
        for (uint8_t i = 0; i < N_FEATURES; i++) {
            char buffer[64], zcr_s[15], ste_s[15];
            dtostrf(zcr_out[i], 6, 4, zcr_s); 
            dtostrf(ste_out[i], 8, 4, ste_s);
            sprintf(buffer, "Frame %d -> ZCR: %s, STE: %s\n", i, zcr_s, ste_s);
            UART_send_string(buffer);
        }
        UART_send_string("---END---\n");
        
        for(volatile long delay = 0; delay < 100000; delay++); 
    }
    return 0;
}