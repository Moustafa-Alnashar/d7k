#define F_CPU 11059200UL

#include <stdio.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/pgmspace.h>
#include <util/delay.h>
#include <math.h>

#include "adc.h"
#include "uart.h"
#include "lcd.h"
#include "word_templates.h"

#define LED1 PB1
#define LED2 PB2
#define LED3 PB3
#define LED4 PB4
#define BUTTON_PIN PB0
#define MIC 0

int8_t true_dc_offset = 128;

// --- Global Sampling Volatiles ---
volatile uint8_t sample_ready = 0;
volatile uint8_t current_raw_sample = 0;

// --- Timer 1 ISR (Triggers at exactly 8 kHz) ---
ISR(TIMER1_COMPA_vect) {
    // Read your high 8-bits from the ADC
    current_raw_sample = ADC_Read_H(MIC);
    sample_ready = 1;
}

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

// --- Distance Classification (Updated to support Multi-Template format) ---
int8_t classify_word(float* input_zcr, float* input_ste) {
    float min_dist = 1000000.0f; 
    int8_t predicted_label = -1;

    // Fix: Python script now exports TOTAL_TEMPLATES (e.g. 16), not just N_WORDS (8)
    for (uint8_t j = 0; j < TOTAL_TEMPLATES; j++) {
        float dist_zcr = 0;
        float dist_ste = 0;

        for (uint8_t f = 0; f < N_FEATURES; f++) {
            float temp_zcr = pgm_read_float(&(zcr_templates[j][f]));
            float temp_ste = pgm_read_float(&(ste_templates[j][f]));

            dist_zcr += fabsf(input_zcr[f] - temp_zcr);
            dist_ste += fabsf(input_ste[f] - temp_ste);
        }

        float total_dist = (W_ZCR * dist_zcr) + (W_STE * dist_ste);

        if (total_dist < min_dist) {
            min_dist = total_dist;
            // Map the template array index back to the underlying word ID
            predicted_label = pgm_read_byte(&(template_labels[j]));
        }
    }
    return predicted_label;
}

// v2
void capture_audio_features(float* zcr_out, float* ste_out) {
    printf("START_STREAM\n");
    float last_centered = 0.0f;
    float last_sample = 0.0f;
    for (uint8_t frame = 0; frame < N_FEATURES; frame++) {
        float energy = 0.0f;
        uint8_t zero_crossings = 0;


        for (uint8_t i = 0; i < 128; i++) {
            // Wait for the hardware timer to tick
            while (!sample_ready);
            sample_ready = 0; // Clear flag

            uint8_t reading = current_raw_sample;
            UART_put_uint8_t(reading);
            
            int8_t centered_i8 = (int8_t)((int16_t)reading - true_dc_offset);
            uint8_t centered_u8 = (uint8_t)centered_i8;
            float centered = ((float)centered_u8 - 128.0f) / 128.0f;

//            float centered = ((float)reading - (float)true_dc_offset) / 128.0f;

            float sample = centered - .95f * last_centered;
            sample /= 1.95f;
            
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
        ste_out[frame] = energy / 128.0f;
    }
}

void calibrate_mic() {
    uint32_t dc_sum = 0;
    for(int i = 0; i < 1024; i++) {
        dc_sum += ADC_Read_H(MIC);
        _delay_us(125); // Sample at roughly 8kHz manually for initial offset
    }
    true_dc_offset = (int8_t)(dc_sum >> 10);
}

static FILE uart_str = FDEV_SETUP_STREAM(UART_putChar, UART_getChar, _FDEV_SETUP_RW);

int main(void) {
    LCD_Init();
    LCD_Clear();
    char lcd_buffer[17];
    
    sprintf(lcd_buffer, "Welcome");
    LCD_String_xy(0,0, lcd_buffer);
    
    UART_Init(115200);
    stdin = stdout = &uart_str;

    ADC_Init();
    DDRB |= (1 << LED1) | (1 << LED2) | (1 << LED3) | (1 << LED4);
    
//    calibrate_mic();
    
    // Initialize our precision timer pacing
    timer1_init_8khz();
    
    // Globally enable hardware interrupts
    sei();
    
    float current_zcr[N_FEATURES]; 
    float current_ste[N_FEATURES];
//    int8_t prev_word_id = -1;

    while (1) {
//        if (PINB & (1 << BUTTON_PIN)) continue;
        LCD_Clear(); 
        sprintf(lcd_buffer, "Talk in");
        LCD_String_xy(0,0, lcd_buffer);
        _delay_ms(500);
        
        for(int i = 3; i > 0; i--){
            sprintf(lcd_buffer, "%i", i);
            LCD_String_xy(0,8, lcd_buffer);
            _delay_ms(500);
        }
        
        LCD_Clear(); 
        sprintf(lcd_buffer, "Talk now!");
        LCD_String_xy(0,0, lcd_buffer);
        
        capture_audio_features(current_zcr, current_ste);
        
        int8_t word_id = classify_word(current_zcr, current_ste);
        
        if (word_id >= 0 && word_id < N_WORDS) {
//            printf("word is %s\n", words[word_id]);
//            printf("with id %i\n", word_id);

//            PORTB = ~(word_id << 1);
            
//            if(word_id != prev_word_id){
                LCD_Clear();
                
                sprintf(lcd_buffer, "id %i Word is", word_id);
                LCD_String_xy(0,0, lcd_buffer);

                sprintf(lcd_buffer, words[word_id]);
                LCD_String_xy(1, 0, lcd_buffer);
                
//                prev_word_id = word_id;
//            }
        }
        _delay_ms(2000);
    }
}