#!/usr/bin/env python3

from time import sleep

from colored import attr, fg
from pendulum import now
from vtclear import clear_screen

# Bold normal yellow.
bold_yellow = attr("bold") + fg(11)

style_reset = attr("reset")


class Chronos:
    def __get_city(self, tz):
        return tz.split("/")[1]

    def print_time_screen(self):
        """It show the time screens with all the clocks."""

        timezones_to_show = [
            "America/Buenos_Aires",
            "America/Caracas",
            "America/La_Paz",
            "America/Lima",
            "America/Los_Angeles",
            "America/Montevideo",
            "America/New_York",
            "America/Sao_Paulo",
            "Asia/Bangkok",
            "Asia/Dubai",
            "Asia/Hong_Kong",
            "Asia/Istanbul",
            "Asia/Tokyo",
            "Asia/Vladivostok",
            "Atlantic/Bermuda",
            "Atlantic/Canary",
            "Australia/Sydney",
            "Europe/London",
            "Europe/Madrid",
            "Europe/Moscow",
            "Europe/Rome",
            "Pacific/Honolulu",
        ]

        half_number_of_tzones = int(len(timezones_to_show) / 2)

        while True:
            clear_screen()
            local = now()

            local_text = local.format("YYYY-MM-DD HH:mm:ss")
            local_tz = self.__get_city(local.tzinfo.name)
            print(
                f"{bold_yellow}LOCAL [{local_tz}]: {local_text}{style_reset}"
                )

            world_times = [[], []]

            for i in range(len(timezones_to_show)):
                city = self.__get_city(timezones_to_show[i])
                time_to_show = now(
                    timezones_to_show[i]
                    ).format("HH:mm:ss")

                if i >= half_number_of_tzones:
                    column = 1
                else:
                    column = 0

                world_times[column].append(f"{city}: {time_to_show}")

            longest_column = 0
            for column in world_times:
                if len(column) > longest_column:
                    longest_column = len(column)

            for row in range(longest_column):
                if row < len(world_times[0]):
                    first_column = world_times[0][row].replace("_", " ")
                else:
                    first_column = ""

                if row < len(world_times[1]):
                    second_column = world_times[1][row].replace("_", " ")
                else:
                    second_column = ""

                whitespace = " " * (25 - len(first_column))

                print(f"{first_column}{whitespace} {second_column}")

            sleep(1)


def main():
    chronos = Chronos()
    chronos.print_time_screen()
