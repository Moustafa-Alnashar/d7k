#include <avr/io.h>
#include "adc.h"

void ADC_Init() {
    // REFS0: AVCC ref, ADLAR: Left Adjust for 8-bit output in ADCH
    ADMUX = (1 << REFS0) | (1 << ADLAR);
    // Prescaler 32: 11.0592MHz / 128 = 86.4kHz ADC clock (well within 50-200kHz limit)
    ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS0);;
    ADCSRA &= ~(1 << ADPS1);
}

// can be used for reading potentiometer 

uint8_t ADC_Read_H(uint8_t channel) {
    // Select ADC channel with safety mask
    ADMUX = (ADMUX & 0xF8) | (channel & 0x07);
    // Start single conversion
    ADCSRA |= (1 << ADSC);
    // Wait for conversion to complete
    while (ADCSRA & (1 << ADSC));
    return ADCH;
}