'''
This script creates a model using transfer learning and 
images scraped from google.

In order to use this script, run the following from the command line:
python train_mask_detector.py --dataset dataset
'''

# import the necessary packages
import numpy as np
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.models import Model
from tensorflow.keras.layers import AveragePooling2D, Dropout, Flatten, Dense, Input
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import img_to_array, load_img
from tensorflow.keras.utils import to_categorical
from sklearn.preprocessing import LabelBinarizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from imutils import paths
import matplotlib.pyplot as plt
import argparse
import os

plt.style.use('ggplot')

ap = argparse.ArgumentParser()
ap.add_argument("-d", "--dataset", required=True,
    help="path to input dataset")
ap.add_argument("-p", "--plot", type=str, default="plots/plot.png",
    help="path to output loss/accuracy plot")
ap.add_argument("-m", "--model", type=str,
    default="face_mask_detector.model",
    help="path to output face mask detector model")
args = vars(ap.parse_args())

# initialize the initial learning rate, number of epochs to train for,
# and batch size
learning_rate = 1e-3
EPOCHS = 20
BS = 32

# grab the list of images in the dataset directory, then itialize
# the list of images and class images
print("...Loading images from folder...")
imagePaths = list(paths.list_images(args["dataset"]))
data = []
labels = []

# loop over the image paths
for i, imagePath in enumerate(imagePaths):
    # extract the class label from the filename
    label = imagePath.split(os.path.sep)[-2]

    # load the input image (224x224) and preprocess it
    image = load_img(imagePath, target_size=(224,224))
    image = img_to_array(image)
    image = preprocess_input(image)

    # update the data and labels lists, respectively
    data.append(image)
    labels.append(label)

# convert the data and labels to Numpy arrays
data = np.array(data, dtype="float32")
labels = np.array(labels)

# perform one-hot encoding on the labels
lb = LabelBinarizer()
labels = lb.fit_transform(labels)
labels = to_categorical(labels)
#print(labels)

# partition the data into training and testing splits using 20% 
# for testing
X_train, X_test, y_train, y_test = train_test_split(data, labels,
        test_size=0.20, stratify=labels, random_state=42)

# construct the training image generator for data augmentation
train_transformations = ImageDataGenerator(
    rotation_range=15,
    width_shift_range=0.2, 
    height_shift_range=0.2,
    zoom_range=0.10,
    shear_range=0.10,
    horizontal_flip=True,
    fill_mode="nearest"
)

# load the MobileNetV2 network, ensuring the head FC layer sets are 
# left off
base_model = MobileNetV2(weights="imagenet", include_top=False,
        input_tensor=Input(shape=(224,224,3)))

# build model head
head_model = base_model.output
head_model = AveragePooling2D(pool_size=(7,7))(head_model)
head_model = Flatten(name='flatten')(head_model)
head_model = Dense(128, activation='relu')(head_model)
head_model = Dropout(0.50)(head_model)
head_model = Dense(2, activation="softmax")(head_model)

# place the head FC model on top of the base model (this will become 
# the actual model we will train)
model = Model(inputs=base_model.input, outputs=head_model)

# freeze layers from transferred model
for layer in base_model.layers:
    layer.trainable = False 

# compile the model
print("...Compiling model...")
# initalize adam optimizer
opt = Adam(lr = learning_rate, decay = learning_rate / EPOCHS)
model.compile(loss="binary_crossentropy", optimizer=opt,
    metrics=["accuracy"])

# train the head of the network
print("...Training head...")
H = model.fit(
    train_transformations.flow(X_train, y_train, batch_size=BS),
    steps_per_epoch=len(X_train) // BS,
    validation_data = (X_test, y_test),
    validation_steps = len(X_test) // BS,
    epochs=EPOCHS
)

# make predictions on the testing set
print("...Evaluating network...")
predIdxs = model.predict(X_test, batch_size=BS)

# for each image in the testing set we need to find the index
# of the label with corresponding largest predicted probability
predIdxs = np.argmax(predIdxs, axis=1)

# show a nicely formatted classification report
print(classification_report(y_test.argmax(axis=1), predIdxs,
    target_names=lb.classes_))

# serialize the model to disk
print("...Saving mask detector model...")
model.save(args["model"], save_format="h5")

# plot the training loss and accuracy
N = EPOCHS
plt.figure()
plt.plot(np.arange(0,N), H.history["loss"], label="train_loss")
plt.plot(np.arange(0,N), H.history["val_loss"], label="val_loss")
plt.plot(np.arange(0,N), H.history["accuracy"], label="train_acc")
plt.plot(np.arange(0,N), H.history["val_accuracy"], label="val_acc")
plt.xlabel("Epoch #")
plt.ylabel("Loss/Accuracy")
plt.legend(loc="lower left")
plt.savefig(args["plot"])