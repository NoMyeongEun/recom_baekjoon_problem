import os
import random
import numpy as np
import pandas as pd
from tqdm import tqdm
import bottleneck as bn
import torch
import tensorflow as tf
from tensorflow import shape,math
from tensorflow.keras import Input,layers,Model
from tensorflow.keras.losses import mse,binary_crossentropy

import warnings

class EASE:
    """
    Embarrassingly Shallow Autoencoders model class
    """

    def __init__(self, lambda_):
        self.B = None
        self.lambda_ = lambda_

    def train(self, interaction_matrix):
        """
        train pass
        :param interaction_matrix: interaction_matrix
        """
        G = interaction_matrix.T @ interaction_matrix
        diag = list(range(G.shape[0]))
        G[diag, diag] += self.lambda_
        P = np.linalg.inv(G)

        # B = P * (X^T * X − diagMat(γ))
        self.B = P / -np.diag(P)
        min_dim = min(*self.B.shape)
        self.B[range(min_dim), range(min_dim)] = 0

    def forward(self, user_row):
        """
        forward pass
        """
        return user_row @ self.B
    
# network parameters
input_shape = 5539
original_dim= input_shape
intermediate_dim = 512
latent_dim = 2

def encoder():
  inputs = Input(shape=(input_shape,), name='input_shape')

  encoder_hidden = layers.Dense(intermediate_dim, activation='relu', name='encoder_hidden1')(inputs)

  z_mean = layers.Dense(latent_dim, name='z_mean')(encoder_hidden)
  z_log_var = layers.Dense(latent_dim, name='z_log_var')(encoder_hidden)

  def sampling(args):
      z_mean, z_log_var = args
      batch = shape(z_mean)[0]
      dim = shape(z_mean)[1]

      # by default, random_normal has mean = 0 and std = 1.0
      # Reparameterization Trick사용을 위해 Gussian(=normal)분포에서 랜덤변수(sample) ε추출
      epsilon = tf.compat.v2.random.normal(shape=(batch, dim))
      return z_mean + tf.math.exp(0.5 * z_log_var) * epsilon

  #  layers.Lambda API 래핑에 사용할 함수와, 유닛수(n,)를 지정합니다.
  z_sampling = layers.Lambda(sampling, (latent_dim,), name='z_sample')([z_mean, z_log_var])

  # 하나의 입력과 다중충력을 포함하는 encoder 모델을 만듭니다.
  return Model(inputs,[z_mean,z_log_var,z_sampling], name='encoder')

def decoder():

  # 디코더의 입력층을 생성합니다. (Decoder의 입력은 latent입니다)
  input_z = Input(shape=(latent_dim,), name='input_z')

  # 디코더의 hidden층을 생성합니다. 인코더와 동일하게 500개의 유닛을 사용했습니다.
  decoder_hidden = layers.Dense(intermediate_dim, activation='relu', name='decoder_hidden')(input_z)

  # 디코더의 출력층은 인코더 입력벡터 수만큼 유닛을 사용합니다.
  outputs = layers.Dense(original_dim, activation='sigmoid',name='output')(decoder_hidden)

  return Model(input_z, outputs, name='decoder')

def vae():
  # vae는 입력으로 이미지로 들어와 encoder를 통해 z_sampling 되어 decoder로 출력됩니다.
  inputs = Input(shape=(input_shape,), name='input_shape')
  outputs = decoder(encoder(inputs)[2]) #[0]:z_mean, [1]:z_log_var,[2]:z_sampling

  return Model(inputs,outputs, name='vae_mlp')

def vae_loss(x,recon_x):
    # (1)Reconstruct loss (Marginal_likelihood) : Cross-entropy
    z_mean,z_log_var,z_sampling = encoder(x)
    recon_x=decoder(z_sampling)
    reconstruction_loss = binary_crossentropy(x,recon_x)
    #reconstruction_loss = mse(inputs, outputs)
    reconstruction_loss *= original_dim
    # (2) KL divergence(Latent_loss)
    kl_loss = 0.5 * tf.reduce_sum(tf.square(z_mean)+ tf.exp(z_log_var)- z_log_var -1, 1)
    return tf.reduce_mean(reconstruction_loss + kl_loss) #ELBO(=VAE_loss)