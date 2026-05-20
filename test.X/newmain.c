//#define F_CPU 11059200UL
//
//#include <avr/io.h>
//#include <util/delay.h>
//#include <avr/interrupt.h>
//#include <stdio.h>
//#include "lcd.h"
//
//// Define LED Pins based on standard PORTB usage
//// The schematic shows them on PB0 and PB1
//#define LED1 PB0
//#define LED2 PB1
//
//// Global variables for threshold and state management
//volatile uint16_t current_threshold = 342;
//volatile uint8_t force_update = 1; 
//volatile uint8_t send_adc_flag = 0;
//volatile uint8_t toggle_threshold_flag = 0;
//
//// --- UART Functions ---
//void UART_Init(uint16_t baud) 
//{
//    uint16_t ubrr = F_CPU / 16 / baud - 1;
//    UBRRH = (uint8_t)(ubrr >> 8);
//    UBRRL = (uint8_t)ubrr;
//    
//    // Enable Receiver, Transmitter, and Receive Interrupt
//    UCSRB = (1 << RXEN) | (1 << TXEN) | (1 << RXCIE); 
//    // Set frame format: 8 data bits, 1 stop bit
//    UCSRC = (1 << URSEL) | (1 << UCSZ1) | (1 << UCSZ0); 
//}
//
//void UART_TxChar(char data) 
//{
//    // Wait for empty transmit buffer
//    while (!(UCSRA & (1 << UDRE)));
//    // Put data into buffer, sends the data
//    UDR = data;
//}
//
//void UART_SendString(char *str) 
//{
//    while (*str) {
//        UART_TxChar(*(str++));
//    }
//}
//
//// --- UART Receive Interrupt ---
//ISR(USART_RXC_vect) 
//{
//    char cmd = UDR;
//    if (cmd == '1') {
//        current_threshold = 342;
//        force_update = 1;
//        UART_SendString("Threshold set to 342 via UART\r\n");
//    } else if (cmd == '2') {
//        current_threshold = 682;
//        force_update = 1;
//        UART_SendString("Threshold set to 682 via UART\r\n");
//    }
//}
//
//// --- ADC Functions ---
//void ADC_Init() 
//{
//    // Voltage Reference: AVCC with external capacitor at AREF pin
//    ADMUX = (1 << REFS0); 
//    // ADC Enable and prescaler of 128
//    ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS1) | (1 << ADPS0); 
//}
//
//// can be used for reading potentiometer 
//uint16_t ADC_Read(uint8_t channel) 
//{
//    // Select ADC channel with safety mask
//    ADMUX = (ADMUX & 0xF8) | (channel & 0x07);
//    // Start single conversion
//    ADCSRA |= (1 << ADSC);
//    // Wait for conversion to complete
//    while (ADCSRA & (1 << ADSC));
//    return ADC;
//}
//
//// --- External Interrupts Initialization ---
//void INT_Init() 
//{
//    // Trigger on falling edge for INT0 (ISC01=0) and INT1 (ISC11=1)
//    // Trigger on rising edge for INT0 (ISC01=1) and INT1 (ISC11=1)
//    MCUCR |= (1 << ISC11) | (1 << ISC01);
//    // Enable INT0 and INT1
//    GICR |= (1 << INT0) | (1 << INT1);
//}
//
//// --- INT0 Interrupt (Send ADC to UART) ---
//ISR(INT0_vect) 
//{
//    _delay_ms(50); // Software debounce delay
//    if (!(PIND & (1 << PD2))) { // Verify button is still pressed
//        send_adc_flag = 1;
//    }
//}
//
//// --- INT1 Interrupt (Toggle Threshold) ---
//ISR(INT1_vect) 
//{
//    _delay_ms(50); // Software debounce delay
//    if (!(PIND & (1 << PD3))) { // Verify button is still pressed
//        if (current_threshold == 342) {
//            current_threshold = 682;
//        } else {
//            current_threshold = 342;
//        }
//        force_update = 1; // Flag LCD to update
//        
//        // Report new threshold over UART
//        char uart_buf[32];
//        sprintf(uart_buf, "Threshold toggled to: %d\r\n", current_threshold);
//        UART_SendString(uart_buf);
//    }
//}
//
//// --- Main Program ---
//int main(void) 
//{
//    // 1. Setup LEDs (Active Low)
//    DDRB |= (1 << LED1) | (1 << LED2); // Set as Output
//    PORTB |= (1 << LED1) | (1 << LED2); // Turn OFF initially (1 = OFF for active low)
//
//    // 2. Setup Buttons (INT0 on PD2, INT1 on PD3)
//    DDRD &= ~((1 << PD2) | (1 << PD3)); // Set as Input
//    PORTD |= (1 << PD2) | (1 << PD3);   // Enable internal pull-ups
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
//    uint16_t last_adc_value = 0xFFFF; // Initialize with impossible value
//    char lcd_buffer[17];
//
//    while (1) 
//    {
//        // Continuously poll the potentiometer (connected to PA0)
//        uint16_t current_adc = ADC_Read(3);
//
//        // Update LCD and LEDs only if ADC value changes or threshold changes
//        if (current_adc != last_adc_value || force_update) {
//            last_adc_value = current_adc;
//            force_update = 0; // Clear flag
//
//            // Check conditions
//            if (current_adc < current_threshold) {
//                // LED1 ON, LED2 OFF (Active Low: 0 = ON, 1 = OFF)
//                PORTB &= ~(1 << LED1); 
//                PORTB |= (1 << LED2);  
//                
//                sprintf(lcd_buffer, "Below THR= %-4d", current_adc);
//            } else {
//                // LED2 ON, LED1 OFF
//                PORTB |= (1 << LED1);  
//                PORTB &= ~(1 << LED2); 
//                
//                sprintf(lcd_buffer, "Above THR= %-4d", current_adc);
//            }
//
//            // Update Line 1
//            LCD_String_xy(0, 0, lcd_buffer);
//
//            // Update Line 2
//            sprintf(lcd_buffer, "Threshold= %-4d", current_threshold);
//            LCD_String_xy(1, 0, lcd_buffer);
//        }
//
//        // Handle INT0 flag to send ADC value over UART
//        if (send_adc_flag) {
//            send_adc_flag = 0; // Clear flag
//            char uart_tx_buf[32];
//            sprintf(uart_tx_buf, "Alarm Event! ADC Value: %d\r\n", current_adc);
//            UART_SendString(uart_tx_buf);
//        }
//
//        // Small delay to stabilize the polling loop
//        _delay_ms(50); 
//    }
//
//    return 0;
//}
//
//
//
//
//
//
//
//
//
////#define F_CPU 11059200UL
////#include <avr/io.h>
////#include <util/delay.h>
////#include <avr/interrupt.h>
////#include <stdio.h>
////#include "lcd.h"
////
////#define LED1 PB0
////#define LED2 PB1
////
////// --- Global Flags & Variables ---
////volatile uint8_t reset_flag = 0;        // INT0
////volatile uint8_t capture_flag = 0;      // INT1
////volatile uint8_t free_run_mode = 0;     // Toggled by 'F'
////volatile uint8_t uart_cmd = 0;
////
////// --- Helper: Convert ADC to Voltage String ---
////void get_voltage_str(uint16_t adc, char* buf) {
////    float voltage = (adc * 5.0) / 1023.0;
////    // Formatting for "V = x.xxx volt"
////    sprintf(buf, "V = %.3f volt", voltage);
////}
////
////// --- UART & ADC Helpers (From your code) ---
////void UART_Init(uint16_t baud) {
////    uint16_t ubrr = F_CPU / 16 / baud - 1;
////    UBRRH = (uint8_t)(ubrr >> 8); UBRRL = (uint8_t)ubrr;
////    UCSRB = (1 << RXEN) | (1 << TXEN) | (1 << RXCIE);
////    UCSRC = (1 << URSEL) | (1 << UCSZ1) | (1 << UCSZ0);
////}
////
////void UART_TxChar(char data) { while (!(UCSRA & (1 << UDRE))); UDR = data; }
////void UART_SendString(char *str) { while (*str) UART_TxChar(*(str++)); }
////
////void ADC_Init() {
////    ADMUX = (1 << REFS0); 
////    ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS1) | (1 << ADPS0); 
////}
////
////uint16_t ADC_Read(uint8_t channel) {
////    ADMUX = (ADMUX & 0xF8) | (channel & 0x07);
////    ADCSRA |= (1 << ADSC);
////    while (ADCSRA & (1 << ADSC));
////    return ADC;
////}
////
////// --- Interrupts ---
////void INT_Init() {
////    MCUCR |= (1 << ISC11) | (1 << ISC01); // Falling Edge
////    GICR |= (1 << INT0) | (1 << INT1);
////}
////
////ISR(INT0_vect) { reset_flag = 1; GICR &= ~(1 << INT0); }
////ISR(INT1_vect) { capture_flag = 1; GICR &= ~(1 << INT1); }
////
////ISR(USART_RXC_vect) { uart_cmd = UDR; }
////
////// --- Main Program ---
////int main(void) {
////    DDRB |= (1 << LED1) | (1 << LED2);
////    PORTB |= (1 << LED1) | (1 << LED2); // LEDs OFF (Active Low)
////    DDRD &= ~((1 << PD2) | (1 << PD3));
////    PORTD |= (1 << PD2) | (1 << PD3);
////
////    LCD_Init();
////    UART_Init(9600);
////    ADC_Init();
////    INT_Init();
////    sei();
////
////    uint16_t adc_val;
////    uint32_t adc_sum = 0;
////    uint8_t poll_count = 0;
////    char line1[17], line2[17], uart_buf[50];
////
////    while (1) {
////        // 1. Check UART Commands
////        if (uart_cmd) {
////            if (uart_cmd == 'G' || uart_cmd == 'g') {
////                adc_val = ADC_Read(3);
////                float v = (adc_val * 5.0) / 1023.0;
////                const char* zone = (adc_val < 342) ? "Low" : (adc_val < 683) ? "Mid" : "High";
////                sprintf(uart_buf, "%s POT voltage = %.3f volt\r\n", zone, v);
////                UART_SendString(uart_buf);
////            } 
////            else if (uart_cmd == 'R' || uart_cmd == 'r') { reset_flag = 1; }
////            else if (uart_cmd == 'F' || uart_cmd == 'f') { free_run_mode = !free_run_mode; }
////            uart_cmd = 0;
////        }
////
////        // 2. Handle INT0 (Reset)
////        if (reset_flag) {
////            LCD_Clear();
////            PORTB |= (1 << LED1) | (1 << LED2);
////            UART_SendString("RESET\r\n");
////            _delay_ms(200);
////            GIFR |= (1 << INTF0); reset_flag = 0; GICR |= (1 << INT0);
////        }
////
////        // 3. Handle Free Running Mode (Requirement 11)
////        if (free_run_mode) {
////            uint32_t free_sum = 0;
////            for(int i=0; i<10; i++) {
////                free_sum += ADC_Read(3);
////                _delay_ms(100);
////            }
////            uint16_t avg = free_sum / 10;
////            sprintf(line1, "AVG ADC= %d", avg);
////            get_voltage_str(avg, line2);
////            LCD_String_xy(0,0, line1);
////            LCD_String_xy(1,0, line2);
////        } 
////        else {
////            // 4. Standard Polling & Zone Logic
////            adc_val = ADC_Read(3);
////            adc_sum += adc_val;
////            poll_count++;
////
////            // Requirement 4, 5, 6: LED & LCD Zones
////            if (adc_val < 342) {
////                PORTB &= ~(1 << LED1); PORTB |= (1 << LED2);
////                sprintf(line1, "Low ADC=%-4d", adc_val);
////            } else if (adc_val < 683) {
////                PORTB &= ~((1 << LED1) | (1 << LED2));
////                sprintf(line1, "Mid ADC=%-4d", adc_val);
////            } else {
////                PORTB |= (1 << LED1); PORTB &= ~(1 << LED2);
////                sprintf(line1, "High ADC=%-4d", adc_val);
////            }
////            
////            get_voltage_str(adc_val, line2);
////            LCD_String_xy(0,0, line1);
////            LCD_String_xy(1,0, line2);
////
////            // Requirement 8: UART transmit every 10 cycles
////            if (poll_count >= 10) {
////                sprintf(uart_buf, "10-Sample Avg: %lu\r\n", adc_sum / 10);
////                UART_SendString(uart_buf);
////                poll_count = 0; adc_sum = 0;
////            }
////        }
////
////        // 5. Handle INT1 (Capture) - Requirement 3
////        if (capture_flag) {
////            uint16_t captured = ADC_Read(3);
////            sprintf(uart_buf, "Captured ADC: %d\r\n", captured);
////            UART_SendString(uart_buf);
////            _delay_ms(200);
////            GIFR |= (1 << INTF1); capture_flag = 0; GICR |= (1 << INT1);
////        }
////
////        _delay_ms(50);
////    }
////}