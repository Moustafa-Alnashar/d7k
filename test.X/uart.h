/* 
 * File:   uart.h
 * Author: alnas
 *
 * Created on May 8, 2026, 3:10 PM
 */

#ifndef UART_H
#define	UART_H

#ifdef	__cplusplus
extern "C" {
#endif

void UART_Init(uint32_t baud);

int UART_getChar(FILE *stream);

int UART_putChar(char data, FILE *stream);

int UART_put_uint8_t(uint8_t data);


#ifdef	__cplusplus
}
#endif

#endif	/* UART_H */

