/* 
 * File:   adc.h
 * Author: alnas
 *
 * Created on May 8, 2026, 3:12 PM
 */

#ifndef ADC_H
#define	ADC_H

#ifdef	__cplusplus
extern "C" {
#endif

void ADC_Init();

uint8_t ADC_Read_H(uint8_t channel);

#ifdef	__cplusplus
}
#endif

#endif	/* ADC_H */

