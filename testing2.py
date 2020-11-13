def make_chocolate(small, big, goal):
	print((goal - min(big, goal // 5) * 5))
	return (-1, (goal - min(big, goal // 5) * 5))[(big >= goal // 5 >= 0) and ((goal - min(big, goal // 5) * 5) <= small)]


print(make_chocolate(6, 1, 11))

