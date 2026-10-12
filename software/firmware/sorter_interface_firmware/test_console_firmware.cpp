/*
 * RP2040 Distribution Board Test Console Firmware
 * Interactive Serial Console for testing hardware channels, steppers,
 * PWM outputs, servos, digital inputs, and TMC2209 drivers.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <array>

#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/bootrom.h"
#include "hardware/pwm.h"
#include "hardware/timer.h"
#include "hardware/adc.h"
#include "hardware/i2c.h"
#include "hardware/watchdog.h"
#if defined(HW_BASICALLY_V1_3)
#include "hwcfg_basically_v1_3.h"
#elif defined(HW_BASICALLY_V1_2)
#include "hwcfg_basically_v1_2.h"
#elif defined(HW_BASICALLY_V1_1)
#include "hwcfg_basically_v1_1.h"
#elif defined(HARDWARE_SKR_PICO)
#include "hwcfg_skr_pico.h"
#else
#include "hwcfg_basically_v1_3.h"
#endif

#include "TMC_UART.h"
#include "TMC2209.h"
#include "Stepper.h"
#include "PCA9685.h"
#include "Servo.h"

// Hardware instances
static std::array<TMC_UART_Bus*, TMC_UART_BUS_COUNT> tmcBuses;
static std::array<TMC2209*, STEPPER_COUNT> tmcDrivers;
static std::array<Stepper*, STEPPER_COUNT> steppers;
static PCA9685* pca9685 = nullptr;

static bool monitoring_inputs = false;
static uint32_t last_input_mask = 0xFFFFFFFF;

// Multicore ticker for steppers
static void core1_entry() {
    uint64_t last_step_time = time_us_64();
    uint64_t last_motion_time = time_us_64();

    while (true) {
        uint64_t now = time_us_64();
        if (now - last_step_time >= (1000000 / STEP_TICK_RATE_HZ)) {
            last_step_time = now;
            for (size_t i = 0; i < STEPPER_COUNT; i++) {
                if (steppers[i]) steppers[i]->stepgen_tick();
            }
        }
        if (now - last_motion_time >= (1000000 / STEP_MOTION_UPDATE_RATE_HZ)) {
            last_motion_time = now;
            for (size_t i = 0; i < STEPPER_COUNT; i++) {
                if (steppers[i]) steppers[i]->motion_update_tick();
            }
        }
        tight_loop_contents();
    }
}

// Hardware initialization
static void init_hardware() {
    stdio_init_all();
    adc_init();
    adc_set_temp_sensor_enabled(true);

    // Initialize Digital Outputs (MOSFET / PWM)
    for (uint8_t i = 0; i < DIGITAL_OUTPUT_COUNT; i++) {
        uint pin = digital_output_pins[i];
        gpio_set_function(pin, GPIO_FUNC_PWM);
        uint slice = pwm_gpio_to_slice_num(pin);
        pwm_config config = pwm_get_default_config();
        pwm_config_set_clkdiv(&config, 4.0f);
        pwm_init(slice, &config, true);
        pwm_set_gpio_level(pin, 0);
    }

    // Initialize Digital Inputs (Limit switches / Hall sensors)
    for (uint8_t i = 0; i < DIGITAL_INPUT_COUNT; i++) {
        uint pin = digital_input_pins[i];
        gpio_init(pin);
        gpio_set_dir(pin, GPIO_IN);
        gpio_pull_up(pin);
    }

    // Initialize DIAG / StallGuard pins
    for (uint8_t i = 0; i < STEPPER_COUNT; i++) {
        uint pin = STEPPER_DIAG_PINS[i];
        gpio_init(pin);
        gpio_set_dir(pin, GPIO_IN);
        gpio_pull_down(pin);
    }

    // Initialize TMC UART Buses
    for (uint8_t i = 0; i < TMC_UART_BUS_COUNT; i++) {
        tmcBuses[i] = new TMC_UART_Bus(TMC_UART_BUSES[i]);
        tmcBuses[i]->setupComm(TMC_UART_BAUDRATE, TMC_UART_BUS_TX_PINS[i], TMC_UART_BUS_RX_PINS[i]);
    }

    // Initialize Steppers & Drivers
    for (uint8_t i = 0; i < STEPPER_COUNT; i++) {
        if (STEPPER_nEN_PINS[i] >= 0) {
            gpio_init(STEPPER_nEN_PINS[i]);
            gpio_set_dir(STEPPER_nEN_PINS[i], GPIO_OUT);
            gpio_put(STEPPER_nEN_PINS[i], 0); // 0V = Active LOW Enable for TMC2209
        }

        uint8_t busIdx = TMC_UART_BUS_INDEX[i];
        uint8_t addr = TMC_UART_ADDRESSES[i];
        tmcDrivers[i] = new TMC2209(tmcBuses[busIdx], addr, 100);
        tmcDrivers[i]->initialize();
        tmcDrivers[i]->setCurrent(16, 8, 10); // Safe default current
        tmcDrivers[i]->setMicrosteps(MICROSTEP_16);
        tmcDrivers[i]->enableDriver(true);

        steppers[i] = new Stepper(STEPPER_STEP_PINS[i], STEPPER_DIR_PINS[i]);
        steppers[i]->initialize();
        steppers[i]->setSpeedLimits(100, 10000);
        steppers[i]->setAcceleration(20000);
    }

    // Initialize I2C Servos (PCA9685)
    i2c_init(I2C_PORT, 400 * 1000);
    gpio_set_function(I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_PIN);
    gpio_pull_up(I2C_SCL_PIN);

    pca9685 = new PCA9685(SERVO_I2C_ADDRESS, I2C_PORT);
    if (pca9685->initialize()) {
        pca9685->setPWMFreq(50); // Standard 50Hz RC servo PWM
    }

    multicore_launch_core1(core1_entry);
}

// Helper to convert servo angle (0..180 deg) to PCA9685 12-bit PWM duty (0..4095)
static uint16_t angle_to_pca_duty(float angle_deg) {
    if (angle_deg < 0.0f) angle_deg = 0.0f;
    if (angle_deg > 180.0f) angle_deg = 180.0f;
    // 50Hz period = 20ms = 4096 ticks
    // 0.5ms (0 deg) -> 102 ticks, 2.5ms (180 deg) -> 512 ticks
    return (uint16_t)(102 + (angle_deg * 410.0f) / 180.0f);
}

// Print banner and help
static void print_banner() {
    printf("\n=====================================================\n");
    printf("   RP2040 Distribution Board - Test Console v1.0    \n");
    printf("   Hardware ID: %s | Steppers: %d | PWM Outputs: %d   \n", HW_ID, STEPPER_COUNT, DIGITAL_OUTPUT_COUNT);
    printf("=====================================================\n");
    printf("Tapez 'help' ou '?' pour la liste des commandes.\n\n");
}

static void print_help() {
    printf("\n=== RP2040 Distribution Board Test Console - HELP ===\n\n");
    printf("Commandes Generales:\n");
    printf("  help / ?                   Afficher ce menu d'aide\n");
    printf("  status                     Afficher l'etat general de la carte (temp, uptime, E/S)\n");
    printf("  reboot [bootloader]        Redemarrer le RP2040 (ou entrer en mode USB BOOTSEL)\n\n");

    printf("Commandes Stepper (Canaux 0 à %d):\n", STEPPER_COUNT - 1);
    printf("  stepper status             Afficher l'etat des 5 moteurs pas-a-pas\n");
    printf("  stepper enable <ch|all>    Activer le driver du canal <ch>\n");
    printf("  stepper disable <ch|all>   Desactiver le driver du canal <ch>\n");
    printf("  stepper move <ch> <steps> [speed_sps]\n");
    printf("                             Effectuer un deplacement de <steps> (relatif +/-)\n");
    printf("  stepper run <ch> <speed>   Faire tourner le moteur <ch> en continu à <speed> pas/s\n");
    printf("  stepper stop <ch|all>      Arreter la rotation du moteur <ch>\n");
    printf("  stepper current <ch> <mA>  Changer le courant du TMC2209 en mA (ex: 600)\n");
    printf("  stepper usteps <ch> <N>    Fixer la resolution des micropas (1, 2, 4, 8, 16, 32, 64, 128, 256)\n");
    printf("  stepper diag               Lire les broches StallGuard / DIAG\n\n");

    printf("Commandes PWM / MOSFET (Leds & Sorties Power):\n");
    printf("  pwm set <ch> <0..100>      Regler la puissance PWM d'une sortie en %%\n");
    printf("  pwm off                    Eteindre toutes les sorties PWM\n\n");

    printf("Commandes Servomoteurs I2C (PCA9685 - Canaux 0 à 15):\n");
    printf("  servo scan                 Scanner le bus I2C (SDA=%d, SCL=%d) pour PCA9685\n", I2C_SDA_PIN, I2C_SCL_PIN);
    printf("  servo clock <int|ext> [hz] Selectionner l'horloge PCA9685 (ext=EXTCLK pin Y1 25MHz vs int=Interne)\n");
    printf("  servo set <ch> <deg 0..180> Positionner le servo <ch> à l'angle specifie\n");
    printf("  servo sweep <ch>           Effectuer un aller-retour automatique de test (0° -> 180° -> 0°)\n\n");

    printf("Entrees Numeriques & Diagnostic:\n");
    printf("  inputs                     Lire l'etat instantane des entrees numeriques (GP2, GP3, DIAG)\n");
    printf("  monitor                    Surveillance en temps reel des changements d'entrees (Entree pour quitter)\n");
    printf("  test all                   Lancer la sequence d'auto-test automatique de toutes les fonctions\n\n");
}

static float read_temperature() {
    adc_select_input(4);
    uint16_t raw = adc_read();
    float voltage = raw * 3.3f / (1 << 12);
    return 27.0f - (voltage - 0.706f) / 0.001721f;
}

static void print_status() {
    printf("\n--- BOARD STATUS ---\n");
    printf("Hardware Target:  %s\n", HW_ID);
    printf("Uptime:           %llu sec\n", time_us_64() / 1000000ULL);
    printf("RP2040 Temp:      %.1f °C\n", read_temperature());

    printf("\n--- DIGITAL INPUTS ---\n");
    for (uint8_t i = 0; i < DIGITAL_INPUT_COUNT; i++) {
        uint pin = digital_input_pins[i];
        printf("  Input Ch %d (GP%d): %s\n", i, pin, gpio_get(pin) ? "HIGH (Open)" : "LOW (Triggered)");
    }

    printf("\n--- DIAG / STALLGUARD PINS ---\n");
    for (uint8_t i = 0; i < STEPPER_COUNT; i++) {
        uint pin = STEPPER_DIAG_PINS[i];
        printf("  Stepper %d DIAG (GP%d): %s\n", i, pin, gpio_get(pin) ? "HIGH (Stall Detected)" : "LOW (Clear)");
    }

    printf("\n--- PWM OUTPUTS ---\n");
    for (uint8_t i = 0; i < DIGITAL_OUTPUT_COUNT; i++) {
        uint pin = digital_output_pins[i];
        printf("  PWM Ch %d (GP%d): configured\n", i, pin);
    }

    printf("\n--- SERVO CONTROLLER (PCA9685) ---\n");
    if (pca9685) {
        printf("  Clock Source:   %s (%lu Hz)\n",
            pca9685->isExternalClock() ? "EXTERNE (Pin EXTCLK / Osc Y1)" : "INTERNE (25MHz)",
            pca9685->getClockFreq());
    } else {
        printf("  PCA9685:        Non Detecte sur I2C1\n");
    }
    printf("\n");
}

static void handle_stepper_cmd(int argc, char* argv[]) {
    if (argc < 2 || strcmp(argv[1], "status") == 0) {
        printf("\n--- STEPPER MOTORS STATUS ---\n");
        for (int i = 0; i < STEPPER_COUNT; i++) {
            printf("Ch %d [%s]: Pos=%ld, Stopped=%s, StepGP=%d, DirGP=%d, DiagGP=%d\n",
                i, STEPPER_NAMES[i],
                steppers[i]->getPosition(),
                steppers[i]->isStopped() ? "YES" : "NO",
                STEPPER_STEP_PINS[i], STEPPER_DIR_PINS[i], STEPPER_DIAG_PINS[i]);
        }
        return;
    }

    if (strcmp(argv[1], "diag") == 0) {
        printf("\n--- STEPPER DIAG / STALLGUARD READOUT ---\n");
        for (int i = 0; i < STEPPER_COUNT; i++) {
            bool state = gpio_get(STEPPER_DIAG_PINS[i]);
            printf("Ch %d [%s] (GP%d): %s\n", i, STEPPER_NAMES[i], STEPPER_DIAG_PINS[i], state ? "TRIGGERED (STALL)" : "OK");
        }
        return;
    }

    if (argc < 3) {
        printf("Erreur: arguments manquants. Voir 'help'.\n");
        return;
    }

    if (strcmp(argv[1], "enable") == 0 || strcmp(argv[1], "disable") == 0) {
        bool en = (strcmp(argv[1], "enable") == 0);
        if (strcmp(argv[2], "all") == 0) {
            for (int i = 0; i < STEPPER_COUNT; i++) {
                tmcDrivers[i]->enableDriver(en);
                if (STEPPER_nEN_PINS[i] >= 0) gpio_put(STEPPER_nEN_PINS[i], en ? 0 : 1);
            }
            printf("Tous les drivers steppers: %s\n", en ? "ACTIVES" : "DESACTIVES");
        } else {
            int ch = atoi(argv[2]);
            if (ch >= 0 && ch < STEPPER_COUNT) {
                tmcDrivers[ch]->enableDriver(en);
                if (STEPPER_nEN_PINS[ch] >= 0) gpio_put(STEPPER_nEN_PINS[ch], en ? 0 : 1);
                printf("Stepper Ch %d [%s]: %s\n", ch, STEPPER_NAMES[ch], en ? "ACTIVE" : "DESACTIVE");
            } else printf("Canal invalide (0..%d)\n", STEPPER_COUNT - 1);
        }
        return;
    }

    if (strcmp(argv[1], "stop") == 0) {
        if (strcmp(argv[2], "all") == 0) {
            for (int i = 0; i < STEPPER_COUNT; i++) steppers[i]->cancel();
            printf("Arrêt d'urgence de tous les steppers.\n");
        } else {
            int ch = atoi(argv[2]);
            if (ch >= 0 && ch < STEPPER_COUNT) {
                steppers[ch]->cancel();
                printf("Stepper Ch %d [%s] arrete.\n", ch, STEPPER_NAMES[ch]);
            }
        }
        return;
    }

    if (strcmp(argv[1], "move") == 0 && argc >= 4) {
        int32_t steps = atol(argv[3]);
        uint32_t spd = (argc >= 5) ? atol(argv[4]) : 2000;
        if (strcmp(argv[2], "all") == 0) {
            for (int i = 0; i < STEPPER_COUNT; i++) {
                tmcDrivers[i]->enableDriver(true);
                if (STEPPER_nEN_PINS[i] >= 0) gpio_put(STEPPER_nEN_PINS[i], 0);
                steppers[i]->setSpeedLimits(100, spd);
                steppers[i]->moveSteps(steps);
            }
            printf("Deplacement de TOUS les steppers de %ld pas lance.\n", steps);
        } else {
            int ch = atoi(argv[2]);
            if (ch >= 0 && ch < STEPPER_COUNT) {
                tmcDrivers[ch]->enableDriver(true);
                if (STEPPER_nEN_PINS[ch] >= 0) gpio_put(STEPPER_nEN_PINS[ch], 0);
                steppers[ch]->setSpeedLimits(100, spd);
                steppers[ch]->moveSteps(steps);
                printf("Deplacement Stepper Ch %d [%s] de %ld pas lance.\n", ch, STEPPER_NAMES[ch], steps);
            } else printf("Canal invalide (0..%d)\n", STEPPER_COUNT - 1);
        }
        return;
    }

    if (strcmp(argv[1], "run") == 0 && argc >= 4) {
        int32_t speed = atol(argv[3]);
        if (strcmp(argv[2], "all") == 0) {
            for (int i = 0; i < STEPPER_COUNT; i++) {
                tmcDrivers[i]->enableDriver(true);
                if (STEPPER_nEN_PINS[i] >= 0) gpio_put(STEPPER_nEN_PINS[i], 0);
                steppers[i]->moveAtSpeed(speed);
            }
            printf("Rotation continue de TOUS les steppers a %ld pas/s.\n", speed);
        } else {
            int ch = atoi(argv[2]);
            if (ch >= 0 && ch < STEPPER_COUNT) {
                tmcDrivers[ch]->enableDriver(true);
                if (STEPPER_nEN_PINS[ch] >= 0) gpio_put(STEPPER_nEN_PINS[ch], 0);
                steppers[ch]->moveAtSpeed(speed);
                printf("Stepper Ch %d [%s] en rotation continue a %ld pas/s.\n", ch, STEPPER_NAMES[ch], speed);
            } else printf("Canal invalide (0..%d)\n", STEPPER_COUNT - 1);
        }
        return;
    }

    if (strcmp(argv[1], "current") == 0 && argc >= 4) {
        int ma = atoi(argv[3]);
        uint8_t runCur = (ma * 31) / 2000;
        if (runCur > 31) runCur = 31;

        if (strcmp(argv[2], "all") == 0) {
            for (int i = 0; i < STEPPER_COUNT; i++) {
                tmcDrivers[i]->setCurrent(runCur, runCur / 2, 10);
            }
            printf("Tous les steppers: courant fixe a %d mA\n", ma);
        } else {
            int ch = atoi(argv[2]);
            if (ch >= 0 && ch < STEPPER_COUNT) {
                tmcDrivers[ch]->setCurrent(runCur, runCur / 2, 10);
                printf("Stepper Ch %d [%s]: courant fixe a %d mA (runCur=%d/31)\n", ch, STEPPER_NAMES[ch], ma, runCur);
            } else printf("Canal invalide (0..%d)\n", STEPPER_COUNT - 1);
        }
        return;
    }

    if (strcmp(argv[1], "usteps") == 0 && argc >= 4) {
        int usteps = atoi(argv[3]);
        TMC2209_Microstep ms = MICROSTEP_16;
        if (usteps == 256) ms = MICROSTEP_256;
        else if (usteps == 128) ms = MICROSTEP_128;
        else if (usteps == 64) ms = MICROSTEP_64;
        else if (usteps == 32) ms = MICROSTEP_32;
        else if (usteps == 16) ms = MICROSTEP_16;
        else if (usteps == 8) ms = MICROSTEP_8;
        else if (usteps == 4) ms = MICROSTEP_4;
        else if (usteps == 2) ms = MICROSTEP_2;
        else if (usteps == 1) ms = MICROSTEP_FULL;

        if (strcmp(argv[2], "all") == 0) {
            for (int i = 0; i < STEPPER_COUNT; i++) {
                tmcDrivers[i]->setMicrosteps(ms);
            }
            printf("Tous les steppers: micropas fixes a 1/%d\n", usteps);
        } else {
            int ch = atoi(argv[2]);
            if (ch >= 0 && ch < STEPPER_COUNT) {
                tmcDrivers[ch]->setMicrosteps(ms);
                printf("Stepper Ch %d [%s]: micropas fixes a 1/%d\n", ch, STEPPER_NAMES[ch], usteps);
            } else printf("Canal invalide (0..%d)\n", STEPPER_COUNT - 1);
        }
        return;
    }

    printf("Commande stepper inconnue. Tapez 'help'.\n");
}

static void handle_pwm_cmd(int argc, char* argv[]) {
    if (argc >= 2 && strcmp(argv[1], "off") == 0) {
        for (uint8_t i = 0; i < DIGITAL_OUTPUT_COUNT; i++) {
            pwm_set_gpio_level(digital_output_pins[i], 0);
        }
        printf("Toutes les sorties PWM sont eteintes.\n");
        return;
    }

    if (argc >= 4 && strcmp(argv[1], "set") == 0) {
        int ch = atoi(argv[2]);
        int duty = atoi(argv[3]);
        if (duty < 0) duty = 0;
        if (duty > 100) duty = 100;

        if (ch >= 0 && ch < DIGITAL_OUTPUT_COUNT) {
            uint pin = digital_output_pins[ch];
            uint16_t level = (duty * 65535) / 100;
            pwm_set_gpio_level(pin, level);
            printf("PWM Ch %d (GP%d) fixe a %d %%\n", ch, pin, duty);
        } else {
            printf("Canal PWM invalide (0..%d)\n", DIGITAL_OUTPUT_COUNT - 1);
        }
        return;
    }

    printf("Usage PWM: pwm set <ch> <0..100> OU pwm off\n");
}

static void handle_servo_cmd(int argc, char* argv[]) {
    if (argc >= 2 && strcmp(argv[1], "scan") == 0) {
        printf("\n--- BALAYAGE BUS I2C (SERVO CONTROLLER) ---\n");
        int count = 0;
        for (uint8_t addr = 0x08; addr < 0x78; addr++) {
            uint8_t rxdata;
            int ret = i2c_read_blocking(I2C_PORT, addr, &rxdata, 1, false);
            if (ret >= 0) {
                printf("  Peripherique trouve a l'adresse 0x%02X %s\n", addr, (addr == SERVO_I2C_ADDRESS) ? "(PCA9685 Servo Controller)" : "");
                count++;
            }
        }
        if (count == 0) printf("Aucun peripherique I2C repondu.\n");
        return;
    }

    if (argc >= 3 && strcmp(argv[1], "clock") == 0) {
        if (!pca9685) {
            printf("Erreur: PCA9685 non initialisé / non détecté.\n");
            return;
        }
        bool use_ext = (strcmp(argv[2], "external") == 0 || strcmp(argv[2], "ext") == 0);
        uint32_t freq = (argc >= 4) ? atol(argv[3]) : 25000000;
        if (pca9685->setClockSource(use_ext, freq)) {
            pca9685->setPWMFreq(50); // recalculate 50Hz prescaler with new clock
            printf("PCA9685: Source d'horloge donnee a %s (%lu Hz)\n",
                use_ext ? "EXTERNE (Pin EXTCLK / Osc Y1)" : "INTERNE (25MHz)", freq);
        } else {
            printf("Erreur lors de la configuration de l'horloge PCA9685.\n");
        }
        return;
    }

    if (argc >= 4 && strcmp(argv[1], "set") == 0) {
        int ch = atoi(argv[2]);
        float angle = atof(argv[3]);
        if (ch >= 0 && ch < 16 && pca9685) {
            uint16_t duty = angle_to_pca_duty(angle);
            pca9685->setPWM(ch, duty);
            printf("Servo Ch %d positionne a %.1f° (duty=%d)\n", ch, angle, duty);
        } else {
            printf("Erreur: Canal servo invalide ou PCA9685 non initialisé.\n");
        }
        return;
    }

    if (argc >= 3 && strcmp(argv[1], "sweep") == 0) {
        int ch = atoi(argv[2]);
        int step_delay_ms = (argc >= 4) ? atoi(argv[3]) : 15; // default 15ms per 2-degree step
        if (step_delay_ms < 5) step_delay_ms = 5;

        if (ch >= 0 && ch < 16 && pca9685) {
            printf("Balayage Servo Ch %d (0° -> 180° -> 0°, step_delay=%dms)...\n", ch, step_delay_ms);
            pca9685->setPWM(ch, angle_to_pca_duty(0.0f));
            sleep_ms(400);

            // Smooth sweep 0° -> 180°
            for (float angle = 0.0f; angle <= 180.0f; angle += 2.0f) {
                pca9685->setPWM(ch, angle_to_pca_duty(angle));
                sleep_ms(step_delay_ms);
            }
            sleep_ms(300);

            // Smooth sweep 180° -> 0°
            for (float angle = 180.0f; angle >= 0.0f; angle -= 2.0f) {
                pca9685->setPWM(ch, angle_to_pca_duty(angle));
                sleep_ms(step_delay_ms);
            }
            printf("Balayage termine.\n");
        }
        return;
    }

    printf("Usage Servo: servo scan | servo set <ch 0..15> <deg> | servo sweep <ch> [step_delay_ms]\n");
}

static void handle_test_all() {
    printf("\n===================================================\n");
    printf("   LANCEMENT DU TEST AUTOMATIQUE DES COMPOSANTS    \n");
    printf("===================================================\n");

    // 1. PWM Test
    printf("\n[1/3] Test des sorties PWM (LEDs / MOSFETs)...\n");
    for (uint8_t i = 0; i < DIGITAL_OUTPUT_COUNT; i++) {
        uint pin = digital_output_pins[i];
        printf("  Testing PWM Ch %d (GP%d)... ", i, pin);
        pwm_set_gpio_level(pin, 32768); // 50%
        sleep_ms(300);
        pwm_set_gpio_level(pin, 65535); // 100%
        sleep_ms(300);
        pwm_set_gpio_level(pin, 0);     // OFF
        printf("OK\n");
    }

    // 2. Servo Test
    printf("\n[2/3] Test des Servomoteurs PCA9685...\n");
    if (pca9685) {
        printf("  Test Servo Ch 0 (Chute/Door)... ");
        pca9685->setPWM(0, angle_to_pca_duty(45.0f));
        sleep_ms(300);
        pca9685->setPWM(0, angle_to_pca_duty(0.0f));
        printf("OK\n");
    } else {
        printf("  PCA9685 non Detecte (Ignoré).\n");
    }

    // 3. Stepper Jog Test
    printf("\n[3/3] Test des Moteurs Pas-a-Pas (Rotation courte)...\n");
    for (int i = 0; i < STEPPER_COUNT; i++) {
        printf("  Jog Stepper Ch %d [%s]... ", i, STEPPER_NAMES[i]);
        tmcDrivers[i]->enableDriver(true);
        if (STEPPER_nEN_PINS[i] >= 0) gpio_put(STEPPER_nEN_PINS[i], 0);
        steppers[i]->moveSteps(200); // 1 full turn forward
        while (!steppers[i]->isStopped()) sleep_ms(10);
        steppers[i]->moveSteps(-200); // 1 full turn back
        while (!steppers[i]->isStopped()) sleep_ms(10);
        printf("OK\n");
    }

    printf("\n===================================================\n");
    printf("   TEST AUTOMATIQUE TERMINE AVEC SUCCES !          \n");
    printf("===================================================\n\n");
}

// Input monitor
static void monitor_inputs_loop() {
    printf("Surveillance active des entrees (Appuyez sur Entrée pour stopper)...\n");
    monitoring_inputs = true;
    while (monitoring_inputs) {
        int c = getchar_timeout_us(0);
        if (c == '\r' || c == '\n') {
            monitoring_inputs = false;
            printf("Fin de surveillance.\n");
            break;
        }

        uint32_t current_mask = 0;
        for (uint8_t i = 0; i < DIGITAL_INPUT_COUNT; i++) {
            if (gpio_get(digital_input_pins[i])) current_mask |= (1 << i);
        }
        for (uint8_t i = 0; i < STEPPER_COUNT; i++) {
            if (gpio_get(STEPPER_DIAG_PINS[i])) current_mask |= (1 << (8 + i));
        }

        if (current_mask != last_input_mask) {
            last_input_mask = current_mask;
            printf("[%llu ms] Changement d'etat Entrees:\n", time_us_64() / 1000);
            for (uint8_t i = 0; i < DIGITAL_INPUT_COUNT; i++) {
                printf("  Digital Input %d (GP%d): %s\n", i, digital_input_pins[i], (current_mask & (1 << i)) ? "HIGH" : "LOW");
            }
            for (uint8_t i = 0; i < STEPPER_COUNT; i++) {
                printf("  Stepper %d DIAG (GP%d): %s\n", i, STEPPER_DIAG_PINS[i], (current_mask & (1 << (8 + i))) ? "STALL" : "OK");
            }
        }
        sleep_ms(20);
    }
}

// Command parser
static void process_line(char* line) {
    // Strip trailing newlines
    char* end = line + strlen(line) - 1;
    while (end >= line && (*end == '\r' || *end == '\n' || isspace(*end))) {
        *end = '\0';
        end--;
    }
    if (strlen(line) == 0) return;

    char* argv[8];
    int argc = 0;
    char* token = strtok(line, " ");
    while (token != NULL && argc < 8) {
        argv[argc++] = token;
        token = strtok(NULL, " ");
    }

    if (argc == 0) return;

    if (strcmp(argv[0], "help") == 0 || strcmp(argv[0], "?") == 0) {
        print_help();
    } else if (strcmp(argv[0], "status") == 0) {
        print_status();
    } else if (strcmp(argv[0], "reboot") == 0) {
        if (argc >= 2 && strcmp(argv[1], "bootloader") == 0) {
            printf("Redemarrage en mode USB BOOTSEL...\n");
            sleep_ms(100);
            reset_usb_boot(0, 0);
        } else {
            printf("Redemarrage du RP2040...\n");
            sleep_ms(100);
            watchdog_reboot(0, 0, 0);
            while (true);
        }
    } else if (strcmp(argv[0], "stepper") == 0) {
        handle_stepper_cmd(argc, argv);
    } else if (strcmp(argv[0], "pwm") == 0) {
        handle_pwm_cmd(argc, argv);
    } else if (strcmp(argv[0], "servo") == 0) {
        handle_servo_cmd(argc, argv);
    } else if (strcmp(argv[0], "inputs") == 0) {
        print_status();
    } else if (strcmp(argv[0], "monitor") == 0) {
        monitor_inputs_loop();
    } else if (strcmp(argv[0], "test") == 0 && argc >= 2 && strcmp(argv[1], "all") == 0) {
        handle_test_all();
    } else {
        printf("Commande inconnue: '%s'. Tapez 'help' pour afficher la liste des commandes.\n", argv[0]);
    }
}

int main() {
    init_hardware();
    sleep_ms(1000);
    print_banner();

    char line_buf[128];
    int line_pos = 0;

    printf("rp2040-test> ");
    fflush(stdout);

    while (true) {
        int c = getchar_timeout_us(0);
        if (c != PICO_ERROR_TIMEOUT) {
            if (c == '\r' || c == '\n') {
                printf("\n");
                line_buf[line_pos] = '\0';
                process_line(line_buf);
                line_pos = 0;
                printf("rp2040-test> ");
                fflush(stdout);
            } else if (c == 8 || c == 127) { // Backspace
                if (line_pos > 0) {
                    line_pos--;
                    printf("\b \b");
                    fflush(stdout);
                }
            } else if (c >= 32 && c <= 126 && line_pos < 127) {
                line_buf[line_pos++] = (char)c;
                putchar(c);
                fflush(stdout);
            }
        }
        tight_loop_contents();
    }

    return 0;
}
