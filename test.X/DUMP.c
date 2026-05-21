//#include <avr/io.h>
//#include <avr/interrupt.h>
//
//#include "lcd.h"
//#include "uart.h"
//#include "adc.h"
//
//// Global variables for threshold and state management
//volatile uint8_t led1_on = 0;
//volatile uint8_t led2_on = 0;
//volatile uint8_t state = 100;
//volatile uint16_t current_adc;
//
//volatile uint8_t force_update = 1;
//volatile uint8_t clear_display_f = 0;
//volatile uint8_t toggle_threshold_flag = 0;
//
//// --- UART Receive Interrupt ---
//
//ISR(USART_RXC_vect) {
//    char cmd = UDR;
//    if (cmd == 'G' || cmd == 'g') {
//
//        force_update = 1;
//        UART_SendString("Threshold set to 342 via UART\r\n");
//    } else if (cmd == '2') {
//
//        force_update = 1;
//        UART_SendString("Threshold set to 682 via UART\r\n");
//    }
//}
//
//// --- External Interrupts Initialization ---
//
//void INT_Init() {
//    // Trigger on falling edge for INT0 (ISC01=0) and INT1 (ISC11=1)
//    // Trigger on rising edge for INT0 (ISC01=1) and INT1 (ISC11=1)
//
//    MCUCR |= (1 << ISC11);
//    MCUCR &= ~(1 << ISC01);
//
//    // Enable INT0 and INT1
//    GICR |= (1 << INT0) | (1 << INT1);
//}
//
//// --- INT0 Interrupt (Send ADC to UART) ---
//
//ISR(INT0_vect) {
//    _delay_ms(50); // Software debounce delay
//    if (!(PIND & (1 << PD2))) { // Verify button is still pressed
//        clear_display_f = 1;
//        led1_on = 0;
//        led2_on = 0;
//
//        state = 3;
//    }
//}
//
//// --- INT1 Interrupt (Toggle Threshold) ---
//
//ISR(INT1_vect) {
//    _delay_ms(50); // Software debounce delay
//    if (!(PIND & (1 << PD3))) { // Verify button is still pressed
//        current_adc = ADC_Read(3);
//
//        if (current_adc < 342) {
//            led1_on = 1;
//            led2_on = 0;
//
//            state = 0;
//
//        } else if (current_adc < 683) {
//            led1_on = 1;
//            led2_on = 1;
//
//            state = 1;
//
//        } else if (current_adc < 1024) {
//            led1_on = 0;
//            led2_on = 1;
//
//            state = 2;
//
//        }
//    }
//}
//
//// --- Main Program ---
//
//int main(void) {
//    // 1. Setup LEDs (Active Low)
//    DDRB |= (1 << LED1) | (1 << LED2); // Set as Output
//    PORTB |= (1 << LED1) | (1 << LED2); // Turn OFF initially (1 = OFF for active low)
//
//    // 2. Setup Buttons (INT0 on PD2, INT1 on PD3)
//    DDRD &= ~((1 << PD2) | (1 << PD3)); // Set as Input
//    PORTD |= (1 << PD2) | (1 << PD3); // Enable internal pull-ups
//
//    // 3. Initialize Peripherals
//    LCD_Init();
//    LCD_Clear();
//    UART_Init(9600); // Set baud rate to 9600
//    ADC_Init();
//    INT_Init();
//
//    // Enable Global Interrupts
//    sei();
//
//    char lcd_buffer[17];
//
//    while (1) {
//        sprintf(lcd_buffer, "%d\n", 5);
//
//        if (led1_on)
//            PORTB &= ~(1 << LED1);
//        else
//            PORTB |= (1 << LED1);
//
//        if (led2_on)
//            PORTB &= ~(1 << LED2);
//        else
//            PORTB |= (1 << LED2);
//
//        switch (state) {
//            case 100: break;
//            case 1: sprintf(lcd_buffer, "LOW ADC= %-4d", current_adc);
//                break;
//            case 2: sprintf(lcd_buffer, "MID ADC= %-4d", current_adc);
//                break;
//            case 3: sprintf(lcd_buffer, "HIGH ADC= %-4d", current_adc);
//                break;
//
//        }
//
//        
//        sprintf(lcd_buffer,"V= %-4d volt", (current_adc - 5) / 1023);
//        LCD_String_xy(1, 0, lcd_buffer);
//
//        UART_SendString(lcd_buffer);
//        if (clear_display_f) {
//            LCD_Clear();
//
//            clear_display_f = 0;
//
//            UART_SendString("Reset\r\n");
//        }
//        LCD_String_xy(0, 0, lcd_buffer);
//    }
//        return 0;
//}
//


//v1
// --- Audio Capture using Non-blocking Interrupt Pacing ---
//void capture_audio_features(float* zcr_out, float* ste_out) {
//    for (uint8_t frame = 0; frame < N_FEATURES; frame++) {
//        uint32_t energy = 0;
//        uint8_t zero_crossings = 0;
//        int8_t last_sample = 0;
//
//        for (uint8_t i = 0; i < 128; i++) {
//            // Wait for the hardware timer to tick
//            while (!sample_ready);
//            sample_ready = 0; // Clear flag
//
//            uint8_t reading = current_raw_sample;
//            UART_put_uint8_t(reading);
//
//            int8_t sample = reading - true_dc_offset;
//            energy += (int16_t)sample * sample;
//
//            if ((sample > 0 && last_sample <= 0) || (sample < 0 && last_sample >= 0)) {
//                zero_crossings++;
//            }
//            last_sample = sample;
//        }
//        
//        zcr_out[frame] = (float)zero_crossings / 128.0f;
//        ste_out[frame] = (float)energy / 2097152.0f; // 128(average) * 128 * 128(normalization)
//    }
//}


//v3
//#define SAMPLES_TO_READ 8000
//#define FRAME_LENGTH 160
//#define HOP_LENGTH 80
//
//void capture_audio_features(float* zcr_out, float* ste_out) {
//    // Dual Accumulators for 50% overlap
//    float ste_A = 0.0f, ste_B = 0.0f;
//    int zcr_A = 0, zcr_B = 0;
//    
//    float last_centered = 0.0f;
//    int last_sign = 0;
//    
//    int frame_index_A = 0; // Even frames
//    int frame_index_B = 1; // Odd frames
//
//    // Zero out the arrays
//    for(int i = 0; i < N_FEATURES; i++) {
//        zcr_out[i] = 0.0f;
//        ste_out[i] = 0.0f;
//    }
//
//    for (int i = 0; i < SAMPLES_TO_READ; i++) {
//        // 1. Wait for hardware Timer/ADC tick
//        while (!sample_ready);
//        sample_ready = 0; 
//        uint8_t reading = current_raw_sample;
//        
//        // Echo to PC
//        UART_put_uint8_t(reading); 
//        
//        // 2. Pre-emphasis Normalization (Librosa equivalent)
//        float centered = ((float)reading - 128.0f) / 128.0f;
//        float sample = centered - 0.95f * last_centered;
//        last_centered = centered;
//
//        // 3. Math for this exact sample
//        int current_sign = (sample > 0.0f);
//        int crossed = 0;
//        if (i > 0 && current_sign != last_sign) {
//            crossed = 1;
//        }
//        last_sign = current_sign;
//
//        float energy = sample * sample;
//
//        // 4. Feed Accumulator A (Frames 0, 2, 4...)
//        int pos_A = i % (FRAME_LENGTH * 2); // Tracks 0 to 319
//        if (pos_A < FRAME_LENGTH) {
//            ste_A += energy;
//            if (pos_A > 0) zcr_A += crossed;
//            
//            // If Accumulator A finishes its 160-sample window
//            if (pos_A == FRAME_LENGTH - 1) {
//                if (frame_index_A < N_FEATURES) {
//                    zcr_out[frame_index_A] = (float)zcr_A / (float)FRAME_LENGTH;
//                    ste_out[frame_index_A] = ste_A / (float)FRAME_LENGTH;
//                }
//                frame_index_A += 2;
//                ste_A = 0.0f; // Reset for the next even frame
//                zcr_A = 0;
//            }
//        }
//
//        // 5. Feed Accumulator B (Frames 1, 3, 5...)
//        // B starts exactly halfway through A's window (80 samples offset)
//        if (i >= HOP_LENGTH) {
//            int pos_B = (i - HOP_LENGTH) % (FRAME_LENGTH * 2); 
//            if (pos_B < FRAME_LENGTH) {
//                ste_B += energy;
//                if (pos_B > 0) zcr_B += crossed;
//                
//                // If Accumulator B finishes its 160-sample window
//                if (pos_B == FRAME_LENGTH - 1) {
//                    if (frame_index_B < N_FEATURES) {
//                        zcr_out[frame_index_B] = (float)zcr_B / (float)FRAME_LENGTH;
//                        ste_out[frame_index_B] = ste_B / (float)FRAME_LENGTH;
//                    }
//                    frame_index_B += 2;
//                    ste_B = 0.0f; // Reset for the next odd frame
//                    zcr_B = 0;
//                }
//            }
//        }
//    }
//
//    // 7. STE Normalization (Divide by max)
//    float max_ste = 0.0f;
//    for (int i = 0; i < N_FEATURES; i++) {
//        if (ste_out[i] > max_ste) {
//            max_ste = ste_out[i];
//        }
//    }
//    if (max_ste > 0.000001f) {
//        for (int i = 0; i < N_FEATURES; i++) {
//            ste_out[i] /= max_ste;
//        }
//    }
//}