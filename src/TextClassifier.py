# from functools import singledispatch
from transformers import BertModel, BertTokenizer
import numpy as np
import torch
import torch.nn as nn
from typing import List, Tuple
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler

from src.TextExtractor import FeaturedText
from LabelTransformer import LabelTransformer


class TrainingData(FeaturedText):
  label: str


class Chapter:
  def __init__(self, title: str, text: str, annotation: str):
    self.title = title
    self.text = text
    self.annotation = annotation


class TextClassifierModel(nn.Module):
  def __init__(self, bert_model_name: str, num_numeric_features: int, num_classes: int):
    super(TextClassifierModel, self).__init__()

    # Pre-trained BERT for text embeddings
    self.bert = BertModel.from_pretrained(bert_model_name)
    self.numeric_features_layer = nn.Linear(num_numeric_features, 128)
    self.combined_layer = nn.Linear(768 + 128, 256)
    self.output_layer = nn.Linear(256, num_classes)
    self.relu = nn.ReLU()

  def forward(self, text: List[str], numeric_features: List[List[float]]):
    # Text embeddings from BERT
    bert_output = self.bert(**text).pooler_output

    # Numeric feature transformation
    numeric_transformed = self.relu(self.numeric_features_layer(numeric_features))

    # Combine both features
    combined = torch.cat((bert_output, numeric_transformed), dim=1)   # Shape: (batch_size, 896)
    combined = self.relu(self.combined_layer(combined))

    # Output prediction
    return self.output_layer(combined)


class TextClassifierPipeline:
  def __init__(self, model_path: str, bert_model_name: str, num_numeric_features: int, num_classes: int):
    self.model_path = Path(model_path) if Path(model_path).exists() else None
    self.tokenizer = BertTokenizer.from_pretrained(bert_model_name)
    self.scaler = MinMaxScaler()
    self.loss_fn = nn.CrossEntropyLoss()
    pretrain_model= False

    # Check if the model exists; otherwise, initialize a new one
    if self.model_path:
      self.model = torch.load(self.model_path)
    else:
      self.model = TextClassifierModel(bert_model_name, num_numeric_features, num_classes)
      self.model_path = Path(model_path)
      pretrain_model = True

    self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-4)

    if pretrain_model:
      training_dataset: List[TrainingData] = [] # load training data
      labels_str = [row["label"] for row in training_dataset]
      label_transformer = LabelTransformer()
      labels = [label_transformer.label_to_int(label) for label in labels_str]
      text_set, feature_set = self.preprocess_input(training_dataset)
      self.__train_model(text_set, feature_set, labels)
      self.save_model(self.model)

  
  def predict(self, text_data: List[str], numeric_features: List[List[float]]):
    self.model.eval()
    with torch.no_grad():
      encoded_text = self.tokenizer(text_data, return_tensor='pt', padding=True, truncation=True)
      numeric_features_tensor = torch.tensor(numeric_features, dtype=torch.float32)
      prediction = self.model(encoded_text, numeric_features_tensor)
      return torch.argmax(prediction, dim=1).tolist()
    
  def save_model(self):
    torch.save(self.model, self.model_path)


  def preprocess_input(self, featured_text: List[FeaturedText]) -> Tuple[List[str], np.ndarray]:
    text_data = [fte['text'] for fte in featured_text]

    numeric_features = [
      [fte['size'], fte['flags'], fte['page']] + list(fte['bbox'])
      for fte in featured_text
    ]

    normalized_features = self.scaler.fit_transform(numeric_features)

    return text_data, normalized_features
  
  def __train_model(self, text_data: List[str], numeric_features: np.ndarray, labels: List[int], epochs=5):
    self.model.train()
    for epoch in range(epochs):
      # Tokenize text data
      encoded_text = self.tokenizer(text_data, return_tensor='pt', padding=True, truncation=True)
      numeric_features_tensor = torch.tensor(numeric_features, dtype=torch.float32)
      labels_tensor = torch.tensor(labels, dtype=torch.int64)

      # Forward pass
      outputs = self.model(encoded_text, numeric_features_tensor)
      loss = self.loss_fn(outputs, labels_tensor)

      # Backward pass and optimization
      self.optimizer.zero_grad()
      loss.backward()
      self.optimizer.step()

      # print(f"Epoch {epoch + 1}/{epochs}, Loss: {loss.item()}")

  

  # @singledispatch
  # def convert(self, text):
  #       raise NotImplementedError("Unsupported type")
  
  # @convert.register
  # def _(self, text: str) -> str:
  #    raise NotImplementedError("Not sure what I want to do here.")

  # @convert.register
  # def _(self, featured_text: FeaturedText) -> str:

  #   df = self.preprocess_data(featured_text)
  #   embeddings = self.extract_text_embeddings(df)
  #   normalized_features = self.extract_numeric_features(df)
  #   # Concatenate normalized features and embeddings - input in classification model
  #   X = np.hstack([normalized_features, embeddings])  # Shape: (n_samples, total_features)
  #   print(len(X))
  #   return 'Done'

  #   # # labels = np.array([0, 1, 0])  # Replace with actual labels

  #   # # Train the classifier
  #   # classifier = RandomForestClassifier()
  #   # classifier.fit(X, labels)

  #   # labels = ['chapter_title', 'main_text', 'annotation', 'other', 'header', 'footer', 'epigraph']  # Example labels; adjust based on training data
  #   # clf = self.train_classifier(df, embeddings, labels)

  #   # # Organize Text
  #   # organized_text = self.organize_text(df, clf)

  #   # return organized_text
    

  # # Step 1: Feature Engineering
  # def preprocess_data(self, data: FeaturedText) -> pd.DataFrame:
  #   df = pd.DataFrame(data)
  #   df['text_length'] = df['text'].apply(len)
  #   df['text_clean'] = df['text'].apply(lambda x: re.sub(r'[^\w\s]', '', x.lower()))
  #   return df

  # # Step 2: NLP Feature Extraction (e.g., embeddings)
  # def extract_text_embeddings(self, df: pd.DataFrame, model_name='all-MiniLM-L6-v2') -> np.ndarray:
  #   model = SentenceTransformer(model_name)
  #   embeddings = model.encode(df['text_clean'].tolist())
  #   scaler = MinMaxScaler()
  #   normalized_embeddings = scaler.fit_transform(embeddings)
  #   return normalized_embeddings

  # def extract_numeric_features(self, df: pd.DataFrame) -> np.ndarray:
  #   scaler = MinMaxScaler()
  #   numeric_features = df[['size', 'page', 'flags', 'text_length']].to_numpy()
  #   bbox_features = np.array(df['bbox'].tolist())
  #   features = np.hstack([bbox_features, numeric_features])
  #   normalized_features = scaler.fit_transform(features)
  #   return normalized_features
    
  # # Step 3: Classification Model
  # def train_classifier(self, df, embeddings, labels):
  #   X_train, X_test, y_train, y_test = train_test_split(embeddings, labels, test_size=0.2, random_state=42)
  #   clf = RandomForestClassifier(n_estimators=100, random_state=42)
  #   clf.fit(X_train, y_train)
  #   y_pred = clf.predict(X_test)
  #   print(classification_report(y_test, y_pred))
  #   return clf

  # # Step 4: Text Grouping and Organization
  # def organize_text(self,df, model):
  #   df['predicted_label'] = model.predict(self.extract_text_embeddings(df))
  #   grouped = df.groupby('page')
  #   chapters = []
  #   for page, group in grouped:
  #     chapter = {"title": "", "main_text": [], "annotations": []}
  #     for _, row in group.iterrows():
  #       if row['predicted_label'] == 'title':
  #         chapter['title'] = row['text']
  #       elif row['predicted_label'] == 'main_text':
  #         chapter['main_text'].append(row['text'])
  #       elif row['predicted_label'] == 'annotation':
  #         chapter['annotations'].append(row['text'])
  #     chapters.append(chapter)
  #   return chapters

