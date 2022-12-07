from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split

from model_inputs import match_info_to_nparray
from db import db_matchinfo_list
import numpy as np

matches = db_matchinfo_list(limit=30000)

for m in matches:
    assert len(m.players) == 10


converted = [match_info_to_nparray(m) for m in matches]

x = np.zeros(shape=(len(matches), 10, 161, 2))

for i in range(len(converted)):
    x[i] = converted[i]

x = x.reshape(len(matches), 161*10*2)
y = np.array([1 if m.winner == 100 else 0 for m in matches])

X_train, X_test, y_train, y_test = train_test_split(x, y, test_size=0.33, random_state=418)

linear = LinearSVC()
linear.fit(X_train, y_train)
print(linear.score(X_test, y_test))