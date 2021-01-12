import csv
import json

# Simple script to convert the underage character CSV into a JSON format.

converted_list = {}

with open('list.csv', encoding='utf8', newline='') as underage_list_csv:
	underage_list = csv.DictReader(underage_list_csv)

	for row in underage_list:
		print(row)
		cur_character = row['Character']

		characters = cur_character.split('/')

		for character in characters:
			converted_list[character.strip().lower()] = {
				"series": row['Series'],
				"age": row['Age'],
				"note": row['Note']
			}

json.dump(converted_list, open('underage.json', 'w'), indent=4)
