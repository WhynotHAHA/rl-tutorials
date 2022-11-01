#!/usr/bin/env python
# coding=utf-8
'''
Author: DingLi
Email: wangzhongren@sjtu.edu.cn
Date: 2022-10-31 22:54:00
LastEditor: DingLi
LastEditTime: 2022-10-31 22:54:25
Discription: CartPole-v1
'''

'''
Author: JiangJi
Email: johnjim0816@gmail.com
Date: 2022-10-12 11:09:54
LastEditor: JiangJi
LastEditTime: 2022-10-30 01:29:25
Discription: CartPole-v1,Acrobot-v1
'''
import sys,os
curr_path = os.path.dirname(os.path.abspath(__file__))  # current path
parent_path = os.path.dirname(curr_path)  # parent path
sys.path.append(parent_path)  # add to system path
import gym
import torch
from torch.autograd import Variable
from common.utils import all_seed,merge_class_attrs
from common.models import MLP
from common.memories import ReplayBuffer, ReplayTree
from common.launcher import Launcher
from envs.register import register_env
from per_dqn import PER_DQN
from config.config import GeneralConfigDQN,AlgoConfigDQN
class Main(Launcher):
    def __init__(self) -> None:
        super().__init__()
        self.cfgs['general_cfg'] = merge_class_attrs(self.cfgs['general_cfg'],GeneralConfigDQN())
        self.cfgs['algo_cfg'] = merge_class_attrs(self.cfgs['algo_cfg'],AlgoConfigDQN())
    def env_agent_config(self,cfg,logger):
        ''' create env and agent
        '''
        register_env(cfg.env_name)
        env = gym.make(cfg.env_name,new_step_api=True)  # create env
        if cfg.seed !=0: # set random seed
            all_seed(env,seed=cfg.seed) 
        try: # state dimension
            n_states = env.observation_space.n # print(hasattr(env.observation_space, 'n'))
        except AttributeError:
            n_states = env.observation_space.shape[0] # print(hasattr(env.observation_space, 'shape'))
        n_actions = env.action_space.n  # action dimension
        logger.info(f"n_states: {n_states}, n_actions: {n_actions}") # print info
        # update to cfg paramters
        setattr(cfg, 'n_states', n_states)
        setattr(cfg, 'n_actions', n_actions)
        # cfg.update({"n_states":n_states,"n_actions":n_actions}) # update to cfg paramters
        model = MLP(n_states,n_actions,hidden_dim=cfg.hidden_dim)
        memory =  ReplayTree(cfg.buffer_size) # replay SumTree
        agent = PER_DQN(model,memory,cfg)  # create agent
        return env, agent

    def train(self,cfg, env, agent,logger):
        ''' 训练
        '''
        logger.info("Start training!")
        logger.info(f"Env: {cfg.env_name}, Algorithm: {cfg.algo_name}, Device: {cfg.device}")
        rewards = []  # record rewards for all episodes
        steps = [] # record steps for all episodes
        for i_ep in range(cfg.train_eps):   
            ep_reward = 0  # reward per episode
            ep_step = 0
            state = env.reset()  # reset and obtain initial state
            for _ in range(cfg.max_steps):
                ep_step += 1
                action = agent.sample_action(state)  # sample action
                next_state, reward, terminated, truncated , info = env.step(action)  # update env and return transitions under new_step_api of OpenAI Gym
                
                target = agent.policy_net(Variable(torch.FloatTensor(state)).cuda()).data
                policy_val = target[action]
                target_val = agent.target_net(Variable(torch.FloatTensor(next_state)).cuda()).data
                if terminated:
                    error = abs(policy_val - reward)
                else:
                    error = abs(policy_val - reward - cfg.gamma * torch.max(target_val))
                agent.memory.push(error.cpu().detach().numpy(), (state, action, reward,
                                next_state, terminated))  # save transitions

                # agent.memory.push(state, action, reward, next_state, terminated)
                state = next_state  # update next state for env
                agent.update()  # update agent
                ep_reward += reward  #
                if terminated:
                    break
            if (i_ep + 1) % cfg.target_update == 0:  # target net update, target_update means "C" in pseucodes
                agent.target_net.load_state_dict(agent.policy_net.state_dict())
            steps.append(ep_step)
            rewards.append(ep_reward)
            logger.info(f'Episode: {i_ep+1}/{cfg.train_eps}, Reward: {ep_reward:.2f}: Epislon: {agent.epsilon:.3f}')
        logger.info("Finish training!")
        env.close()
        res_dic = {'episodes':range(len(rewards)),'rewards':rewards,'steps':steps}
        return res_dic

    def test(self,cfg, env, agent,logger):
        logger.info("Start testing!")
        logger.info(f"Env: {cfg.env_name}, Algorithm: {cfg.algo_name}, Device: {cfg.device}")
        rewards = []  # record rewards for all episodes
        steps = [] # record steps for all episodes
        for i_ep in range(cfg.test_eps):
            ep_reward = 0  # reward per episode
            ep_step = 0
            state = env.reset()  # reset and obtain initial state
            for _ in range(cfg.max_steps):
                ep_step+=1
                action = agent.predict_action(state)  # predict action
                next_state, reward, terminated, _, _ = env.step(action)  
                state = next_state  
                ep_reward += reward 
                if terminated:
                    break
            steps.append(ep_step)
            rewards.append(ep_reward)
            logger.info(f"Episode: {i_ep+1}/{cfg.test_eps}, Reward: {ep_reward:.2f}")
        logger.info("Finish testing!")
        env.close()
        return {'episodes':range(len(rewards)),'rewards':rewards,'steps':steps}


if __name__ == "__main__":
    main = Main()
    main.run()

