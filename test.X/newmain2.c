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
#define MIC 0

const float W_ZCR = 0.6f;
const float W_STE = 0.4f;

// Global variable for calibrated DC offset
int8_t true_dc_offset = 128;
static const char* words[] = {"ana", "tmsah", "famoh", "kabeer", "Chip", "Mega", "Yes", "Zone"};
// --- Distance Calculation ---
int8_t classify_word(float* input_zcr, float* input_ste) {
    float min_dist = 1000000.0f;
    int8_t predicted_label = -1;
    
    for (uint8_t j = 0; j < N_WORDS; j++) {
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
            predicted_label = j;
        }
    }
    return predicted_label;
}

// --- Audio Capture ---
void capture_audio_features(float* zcr_out, float* ste_out) {
    for (uint8_t frame = 0; frame < N_FEATURES; frame++) {
        uint32_t energy = 0;
        uint8_t zero_crossings = 0;
        int8_t last_sample = 0;
        
        for (uint8_t i = 0; i < 128; i++) {
            uint8_t reading = ADC_Read_H(MIC);
            UART_putChar(reading, NULL);
            
            int8_t sample = reading - true_dc_offset;
            
            energy += sample * sample;
            
            if ((sample > 0 && last_sample <= 0) || (sample < 0 && last_sample >= 0)) {
                zero_crossings++;
            }
            last_sample = sample;
            
//            _delay_us(60);
        }

        zcr_out[frame] = (float)zero_crossings / 128.0f;
        ste_out[frame] = (float)energy / 2097152.0f;
    }
}

void calibrate_mic() {
    uint32_t dc_sum = 0;
    for(int i = 0; i < 1024; i++) {
        dc_sum += ADC_Read_H(MIC);
        _delay_us(83); // Sample at roughly 12kHz
    }
    true_dc_offset = (int8_t)(dc_sum >> 10);
}

static FILE uart_str = FDEV_SETUP_STREAM(UART_putChar, UART_getChar, _FDEV_SETUP_RW);

int main(void) {
    LCD_Init();
    LCD_Clear();
    char lcd_buffer[17];

    UART_Init(115200);
    stdin = stdout = &uart_str;

    ADC_Init();
    DDRB |= (1 << LED1) | (1 << LED2) | (1 << LED3) | (1 << LED4);

    // Calibrate the microphone on startup (Keep the room quiet for 0.1 seconds!)
//    calibrate_mic();

    float current_zcr[N_FEATURES];
    float current_ste[N_FEATURES];

    int8_t prev_word_id = -1;

    while (1) {
        // 1. Wait indefinitely until someone actually speaks

        // 2. Capture the features (now perfectly aligned to the start of the word!)
        capture_audio_features(current_zcr, current_ste);

        // 3. Classify
        int8_t word_id = classify_word(current_zcr, current_ste);
//        printf("word is %s\n", words[word_id]);

        // 4. Update LEDs
        PORTB = ~(word_id << 1);

        // 5. Update LCD
        if(word_id != prev_word_id){
            LCD_Clear();

            sprintf(lcd_buffer, "Word is");
            LCD_String_xy(0,0, lcd_buffer);

            sprintf(lcd_buffer, words[word_id]);
            LCD_String_xy(1, 0, lcd_buffer);

            prev_word_id = word_id;
        }
    }
}