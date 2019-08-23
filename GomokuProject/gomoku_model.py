from __future__ import absolute_import, division, print_function, unicode_literals
import tensorflow as tf
from ray.rllib.models.tf.tf_modelv2 import TFModelV2
from ray.rllib.models.tf.misc import normc_initializer
from ray.rllib.models.tf.tf_action_dist import Categorical
import numpy as np

class GomokuModel(TFModelV2):
    def __init__(self, obs_space, action_space, num_outputs, model_config, name):
        super(GomokuModel, self).__init__(obs_space, action_space,num_outputs, model_config, name)
        if 'use_symmetry' in model_config['custom_options']:
            self.use_symmetry = model_config['custom_options']['use_symmetry']
        else:
            self.use_symmetry = False
        input_shp = obs_space.original_space.spaces['real_obs']
        self.inputs = tf.keras.layers.Input(shape=input_shp.shape, name="observations")
        self.outputs = int(np.sqrt(num_outputs))
        layer_0 = tf.keras.layers.Flatten(name='fl')(self.inputs)
        layer_1 = tf.keras.layers.Dense(64, name='_l1', activation=tf.nn.relu,kernel_initializer=normc_initializer(1.0))(layer_0)
        layer_2 = tf.keras.layers.Dense(32,name='_l2', activation=tf.nn.relu,kernel_initializer=normc_initializer(1.0))(layer_1)
        layer_out = tf.keras.layers.Dense(num_outputs, name='_lo', activation=None, kernel_initializer=normc_initializer(0.01))(layer_2)
        value_out = tf.keras.layers.Dense(1, name='_vo', activation=None, kernel_initializer=normc_initializer(0.01))(layer_2)
        self.base_model = tf.keras.Model(self.inputs, [layer_out, value_out])
        self.base_model.summary()
        self.register_variables(self.base_model.variables)

    def get_sym_output(self, board, rotc=0, is_flip=False):
        board_tmp = tf.identity(board)
        for i in range(rotc%4):
            board_tmp = tf.image.rot90(board_tmp)
        if is_flip:
            board_tmp = tf.image.flip_up_down(board_tmp)
        mod_out, val_out = self.base_model(board_tmp)
        model_out_sq = tf.reshape(mod_out, [-1, self.outputs,self.outputs, 1])
        if is_flip:
            model_out_sq = tf.image.flip_up_down(model_out_sq)
        for i in range((4-rotc)%4):
            model_out_sq = tf.image.rot90(model_out_sq)

        model_out_fin = tf.reshape(mod_out, [-1, self.outputs**2])
        value_out_fin = tf.reshape(val_out, [-1])
        return model_out_fin, value_out_fin

    def forward(self, input_dict, state, seq_lens):
        board = input_dict["obs"]["real_obs"]
        if self.use_symmetry:
            model_rot_out = [None]*8
            value_out = [None]*8
            for j in range(2):
                for i in range(4):
                    model_rot_out[j*4+i], value_out[j*4+i] = self.get_sym_output(board, i, j)
            model_out=tf.math.add_n(model_rot_out)
            self.value_out=tf.math.add_n(value_out)
        else:
            model_out, self.value_out = self.base_model(board)
            self.value_out=tf.reshape(self.value_out, [-1])

        inf_mask = tf.maximum(tf.math.log(input_dict["obs"]["action_mask"]), tf.float32.min)
        output = model_out+inf_mask
        return output, state

    def value_function(self):
        return self.value_out


def gen_policy(GENV):
    config = {
        "model": {
            "custom_model": 'GomokuModel',
            "custom_options": {"use_symmetry": False},
            "vf_share_layers": True
        },
        "custom_action_dist": Categorical
    }
    return (None, GENV.observation_space, GENV.action_space, config)

def map_fn(agent_id):
    if agent_id == 'agent_0':
        return 'policy_0'
    else:
        return 'policy_1'