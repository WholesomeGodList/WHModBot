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
			name = character.strip().lower()
			series = row['Series'].split("/")

			for i in range(0, len(series)):
				series[i] = series[i].strip()

			if name in converted_list:
				converted_list[name].append(
					{
						"series": series,
						"age": row['Age'],
						"note": row['Note']
					}
				)
			else:
				converted_list[name] = [
					{
						"series": series,
						"age": row['Age'],
						"note": row['Note']
					}
				]

json.dump(converted_list, open('underage.json', 'w'), indent=4)
