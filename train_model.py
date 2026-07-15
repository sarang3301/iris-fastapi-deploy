"""
train_model.py

Trains a simple scikit-learn classifier on the Iris dataset and
saves it to disk so the FastAPI app can load it at startup.

Run this once before starting the API:
    python train_model.py
"""

import joblib
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

MODEL_PATH = "model/iris_model.joblib"


def train_and_save_model():
    data = load_iris()
    X, y = data.data, data.target

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)

    preds = clf.predict(X_test)
    acc = accuracy_score(y_test, preds)
    print(f"Test accuracy: {acc:.4f}")

    joblib.dump(
        {"model": clf, "target_names": list(data.target_names)},
        MODEL_PATH,
    )
    print(f"Model saved to {MODEL_PATH}")


if __name__ == "__main__":
    train_and_save_model()
