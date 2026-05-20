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
