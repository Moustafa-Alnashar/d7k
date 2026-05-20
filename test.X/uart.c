#define F_CPU 11059200UL

#include <stdio.h>
#include <avr/io.h>
#include "uart.h"

void UART_Init(uint32_t baud) {
    uint16_t ubrr = F_CPU / 16 / baud - 1;

    UBRRH = (uint8_t) (ubrr >> 8);
    UBRRL = (uint8_t) ubrr;

    // Enable Receiver, Transmitter, and Receive Interrupt
    UCSRB = (1 << RXEN) | (1 << TXEN) | (1 << RXCIE);
    // Set frame format: 8 data bits, 1 stop bit
    UCSRC = (1 << URSEL) | (1 << UCSZ1) | (1 << UCSZ0);
}

int UART_getChar(FILE *stream) {
    while ((UCSRA & (1 << RXC)) ==  0);
    return UDR;
}

int UART_putChar(char data, FILE *stream) {
    // Wait for empty transmit buffer
    while (!(UCSRA & (1 << UDRE)));
    // Put data into buffer, sends the data
    UDR = data;
    return 0;
}

int UART_put_uint8_t(uint8_t data) {
    // Wait for empty transmit buffer
    while (!(UCSRA & (1 << UDRE)));
    // Put data into buffer, sends the data
    UDR = data;
    return 0;
}