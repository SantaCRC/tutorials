// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>

/*-----------------------------------------------------------------------*/
/* Uart                                                                  */
/*-----------------------------------------------------------------------*/

static char *readstr(void)
{
	char c[2];
	static char s[64];
	static int ptr = 0;

	if(readchar_nonblock()) {
		c[0] = getchar();
		c[1] = 0;
		switch(c[0]) {
			case 0x7f:
			case 0x08:
				if(ptr > 0) {
					ptr--;
					fputs("\x08 \x08", stdout);
				}
				break;
			case 0x07:
				break;
			case '\r':
			case '\n':
				s[ptr] = 0x00;
				fputs("\n", stdout);
				ptr = 0;
				return s;
			default:
				if(ptr >= (sizeof(s) - 1))
					break;
				fputs(c, stdout);
				s[ptr] = c[0];
				ptr++;
				break;
		}
	}

	return NULL;
}

static char *get_token(char **str)
{
	char *c, *d;

	c = (char *)strchr(*str, ' ');
	if(c == NULL) {
		d = *str;
		*str = *str+strlen(*str);
		return d;
	}
	*c = 0;
	d = *str;
	*str = c+1;
	return d;
}

static void prompt(void)
{
	printf("\e[92;1mlitex-demo-app by Fabian\e[0m> ");
}

/*-----------------------------------------------------------------------*/
/* Help                                                                  */
/*-----------------------------------------------------------------------*/

static void help(void)
{
	puts("\nLiteX minimal demo app by Fabian built "__DATE__" "__TIME__"\n");
	puts("Available commands:");
	puts("help               - Show this command");
	puts("reboot             - Reboot CPU");
#ifdef CSR_LEDS_BASE
	puts("led                - Led demo");
#endif
	puts("donut              - Spinning Donut demo");
	puts("helloc             - Hello C");
#ifdef WITH_CXX
	puts("hellocpp           - Hello C++");
#endif
#ifdef CSR_GPIO_BASE
	puts("gpio               - Enter to GPIO command mode");
#endif
}

/*-----------------------------------------------------------------------*/
/* Commands                                                              */
/*-----------------------------------------------------------------------*/

static void reboot_cmd(void)
{
	ctrl_reset_write(1);
}

// GPIO Control Functions

void set_gpio_bit(uint8_t bit) {
    if (bit > 31) {
        printf("Error: Bit must be between 0 and 31.\n");
        return;
    }

    // 1️⃣ Read the current value of the Output Enable (OE) register
    uint32_t oe_value = gpio_oe_read();

    // 2️⃣ Activate the bit in the OE register (configure the pin as output)
    oe_value |= (1 << bit);

    // 3️⃣ Write the updated value to the OE register
    gpio_oe_write(oe_value);

    // 4️⃣ Read the current output value (in case it was in another state)
    uint32_t current_value = gpio_oe_read();

	// 5️⃣ Set the bit in the GPIO output register

    printf("Bit %d activated as output. Current GPIO_OUT value: 0x%08X\n", bit, current_value);
}


void clear_gpio_bit(uint8_t bit) {
    if (bit > 31) {
        printf("Error: Bit must be between 0 and 31.\n");
        return;
    }

    // Read the current GPIO value
    uint32_t current_value = gpio_out_read();

    // Deactivate the bit using an AND operation with the inverse
    current_value &= ~(1 << bit);

    // Write the updated value to the GPIO
    gpio_out_write(current_value);

    // Console confirmation
    printf("Bit %d deactivated. Current GPIO_OE value: 0x%08X\n", bit, current_value);
}


// GPIO Command Handler

// GPIO Command Handler

static void gpio_cmd(void)
{
    int i = 1;
    while (i)
    {
		printf("\e[92;1mGPIO command mode by Fabian\e[0m> ");
        // Wait for a valid command
        char *str = NULL;
        while (str == NULL) {
            str = readstr();  // Try to read the input
        }

        // Read the first token
        char *token = get_token(&str);

		// write
		if (strcmp(token, "write") == 0) {
			token = get_token(&str);
			if (token == NULL) {
				printf("Error: Missing value.\n");
				continue;
			}
			uint32_t value = strtoul(token, NULL, 0);
			gpio_out_write(value);
			printf("GPIO_OUT set to 0x%08X\n", value);


		// Command: READ
		} else if (strcmp(token, "read") == 0) {
			uint32_t value = gpio_in_read();
			printf("GPIO_IN value: 0x%08X\n", value);
		

        // Command: SET
        }
		else if (strcmp(token, "set") == 0) {
            token = get_token(&str);
            if (token == NULL) {
                printf("Error: Missing bit number.\n");
                continue;
            }
            int bit = atoi(token);
            set_gpio_bit(bit);

        // Command: CLEAR
        } else if (strcmp(token, "clear") == 0) {
            token = get_token(&str);
            if (token == NULL) {
                printf("Error: Missing bit number.\n");
                continue;
            }
            int bit = atoi(token);
            clear_gpio_bit(bit);

        // Command: TOGGLE
        } else if (strcmp(token, "toggle") == 0) {
            token = get_token(&str);
            int bit = atoi(token);
            uint32_t current_value = gpio_out_read();
            current_value ^= (1 << bit);
            gpio_out_write(current_value);
            printf("Bit %d toggled. Current GPIO_OUT value: 0x%08X\n", bit, current_value);

        // Command: DIRECTION
        } else if (strcmp(token, "direction") == 0) {
            token = get_token(&str);
            int bit = atoi(token);
            token = get_token(&str);
            if (strcmp(token, "in") == 0) {
                gpio_oe_write(gpio_oe_read() & ~(1 << bit));
                printf("Bit %d set as input.\n", bit);
            } else if (strcmp(token, "out") == 0) {
                gpio_oe_write(gpio_oe_read() | (1 << bit));
                printf("Bit %d set as output.\n", bit);
            }


        // Command: STATUS
        } else if (strcmp(token, "status") == 0) {
            printf("GPIO Status:\n");
            printf("  Inputs  : 0x%08X\n", gpio_in_read());
            printf("  Outputs : 0x%08X\n", gpio_out_read());
            printf("  Direction (OE): 0x%08X\n", gpio_oe_read());

        // Command: EXIT
        } else if (strcmp(token, "exit") == 0) {
            i = 0;

		// Command: PULSE
		} else if (strcmp(token, "pulse") == 0) {
			token = get_token(&str);
			int bit = atoi(token);
			token = get_token(&str);
			int duration = atoi(token);
			gpio_out_write(gpio_out_read() | (1 << bit));
			busy_wait(duration);
			gpio_out_write(gpio_out_read() & ~(1 << bit));
			printf("Bit %d pulsed for %d ms.\n", bit, duration);

		// Command: BLINK
		} else if (strcmp(token, "blink") == 0) {
			token = get_token(&str);
			int bit = atoi(token);
			token = get_token(&str);
			int count = atoi(token);
			token = get_token(&str);
			int interval = atoi(token);
			for (int j = 0; j < count; j++) {
				gpio_out_write(gpio_out_read() | (1 << bit));
				busy_wait(interval);
				gpio_out_write(gpio_out_read() & ~(1 << bit));
				busy_wait(interval);
			}
			printf("Bit %d blinked %d times with %d ms interval.\n", bit, count, interval);
			

        // Unknown Command
        } else {
            printf("Unknown command: %s\n", token);
			puts("Enter GPIO command:");
			puts("Available commands:");
			puts("  write <value>    - Write value to GPIO_OUT");
			puts("  read             - Read value from GPIO_IN");
			puts("  set <bit>        - Set GPIO bit as output");
			puts("  clear <bit>      - Clear GPIO bit");
			puts("  toggle <bit>     - Toggle GPIO bit");
			puts("  direction <bit> <in|out> - Set GPIO direction");
			puts("  status           - Show GPIO status");
			puts("  pulse <bit> <duration> - Pulse GPIO bit");
			puts("  blink <bit> <count> <interval> - Blink GPIO bit");
			puts("  exit             - Exit GPIO command mode");
			}
    }
}





#ifdef CSR_LEDS_BASE
static void led_cmd(void)
{
	int i;
	printf("Led demo...\n");

	printf("Counter mode...\n");
	for(i=0; i<32; i++) {
		leds_out_write(i);
		busy_wait(100);
	}

	printf("Shift mode...\n");
	for(i=0; i<4; i++) {
		leds_out_write(1<<i);
		busy_wait(200);
	}
	for(i=0; i<4; i++) {
		leds_out_write(1<<(3-i));
		busy_wait(200);
	}

	printf("Dance mode...\n");
	for(i=0; i<4; i++) {
		leds_out_write(0x55);
		busy_wait(200);
		leds_out_write(0xaa);
		busy_wait(200);
	}
}
#endif

extern void donut(void);

static void donut_cmd(void)
{
	printf("Donut demo...\n");
	donut();
}


extern void helloc(void);

static void helloc_cmd(void)
{
	printf("Hello C demo...\n");
	helloc();
}

#ifdef WITH_CXX
extern void hellocpp(void);

static void hellocpp_cmd(void)
{
	printf("Hello C++ demo...\n");
	hellocpp();
}
#endif

/*-----------------------------------------------------------------------*/
/* Console service / Main                                                */
/*-----------------------------------------------------------------------*/

static void console_service(void)
{
	char *str;
	char *token;

	str = readstr();
	if(str == NULL) return;
	token = get_token(&str);
	if(strcmp(token, "help") == 0)
		help();
	else if(strcmp(token, "reboot") == 0)
		reboot_cmd();
#ifdef CSR_LEDS_BASE
	else if(strcmp(token, "led") == 0)
		led_cmd();
#endif
	else if(strcmp(token, "donut") == 0)
		donut_cmd();
	else if(strcmp(token, "helloc") == 0)
		helloc_cmd();
#ifdef WITH_CXX
	else if(strcmp(token, "hellocpp") == 0)
		hellocpp_cmd();
#endif
#ifdef CSR_GPIO_BASE
	else if(strcmp(token, "gpio") == 0) {
		gpio_cmd();
	}
#endif
	prompt();
}

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
	uart_init();

	help();
	prompt();

	while(1) {
		console_service();
	}

	return 0;
}
