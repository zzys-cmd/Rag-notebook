import { defineStore } from 'pinia';
import axios from 'axios';
import { apiConfig } from '../config/api';

// 从cookie中获取CSRF token
const getCsrfToken = () => {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
};

export const useUserStore = defineStore('user', {
  state: () => ({
    userInfo: null,
    token: '',
    isLogin: false,
    userBio: '这是我的个人简介'
  }),
  
  getters: {
    getUserInfo: (state) => state.userInfo,
    getToken: (state) => state.token,
    getLoginStatus: (state) => state.isLogin,
    getUserBio: (state) => state.userInfo?.bio || state.userBio
  },
  
  actions: {
    async login(userData) {
      try {
        // 发送登录请求
        const response = await axios.post(apiConfig.endpoints.login, {
          username: userData.username,
          password: userData.password
        }, {
          headers: {
            'X-CSRFTOKEN': getCsrfToken()
          }
        });
        
        // 检查响应状态
        if (response.status === 200) {
          // 登录成功
          const userInfo = response.data.user;
          // 存储token
          const token = response.data.token;
          // 将token存入到localStorage
          localStorage.setItem('jwt_token', token);
          
          this.userInfo = userInfo;
          this.token = token;
          this.isLogin = true;
          
          return {
            success: true,
            message: response.data.message
          };
        } else {
          // 登录失败
          return {
            success: false,
            message: response.data.detail || '登录失败'
          };
        }
      } catch (error) {
        console.error('登录请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.detail?.non_field_errors?.[0] || '登录请求失败，请稍后再试'
        };
      }
    },
    
    async logout() {
      try {
        // 发送注销请求
        const token = localStorage.getItem('jwt_token') || this.token;
        if (token) {
          await axios.post(apiConfig.endpoints.logout, {}, {
            headers: {
              Authorization: `Bearer ${token}`,
              'X-CSRFTOKEN': getCsrfToken()
            }
          });
        }
      } catch (error) {
        console.error('注销请求失败:', error);
      } finally {
        // 清除本地状态
        this.userInfo = null;
        this.token = '';
        this.isLogin = false;
        // 从localStorage中清除token
        localStorage.removeItem('jwt_token');
      }
    },
    
    // 获取用户信息
    async getUserInfoDetail() {
      try {
        // 从localStorage获取token
        const token = localStorage.getItem('jwt_token') || this.token;
        // 检查是否有token
        if (!token) {
          return {
            success: false,
            message: '未登录'
          };
        }
        
        // 发送获取用户信息请求
        const response = await axios.get(apiConfig.endpoints.profile, {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-CSRFTOKEN': getCsrfToken()
          }
        });
        
        // 检查响应状态
        if (response.status === 200) {
          // 更新用户信息
          this.userInfo = response.data.data;
          
          return {
            success: true,
            message: response.data.message,
            data: response.data.data
          };
        } else {
          return {
            success: false,
            message: response.data.detail || '获取用户信息失败'
          };
        }
      } catch (error) {
        console.error('获取用户信息请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.detail || '获取用户信息请求失败，请稍后再试'
        };
      }
    },
    
    // 更新用户信息
    async updateUserInfo(userData) {
      try {
        // 从localStorage获取token
        const token = localStorage.getItem('jwt_token') || this.token;
        // 检查是否有token
        if (!token) {
          return {
            success: false,
            message: '未登录'
          };
        }
        
        // 发送更新用户信息请求
        console.log('更新用户信息请求参数:', userData);
        const response = await axios.put('/user/update/', userData, {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-CSRFTOKEN': getCsrfToken(),
            'Content-Type': 'application/json'
          }
        });
        
        // 检查响应状态
        if (response.status === 200) {
          // 更新用户信息
          this.userInfo = response.data.user;
          
          // 如果返回了新的token，更新token
          if (response.data.token) {
            this.token = response.data.token;
            localStorage.setItem('jwt_token', response.data.token);
          }
          
          return {
            success: true,
            message: response.data.message
          };
        } else {
          return {
            success: false,
            message: response.data.detail || '更新用户信息失败'
          };
        }
      } catch (error) {
        console.error('更新用户信息请求失败:', error);
        console.error('错误响应:', error.response?.data);
        console.error('错误状态:', error.response?.status);
        return {
          success: false,
          message: error.response?.data?.message || error.response?.data?.detail || '更新用户信息请求失败，请稍后再试'
        };
      }
    },
    
    // 更新密码
    async updatePassword(oldPassword, newPassword) {
      try {
        // 从localStorage获取token
        const token = localStorage.getItem('jwt_token') || this.token;
        // 检查是否有token
        if (!token) {
          return {
            success: false,
            message: '未登录'
          };
        }
        
        // 发送更新密码请求
        const response = await axios.post('/user/change_password/', {
          old_password: oldPassword,
          new_password: newPassword
        }, {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-CSRFTOKEN': getCsrfToken(),
            'Content-Type': 'application/json'
          }
        });
        
        // 检查响应状态
        if (response.status === 200) {
          return {
            success: true,
            message: response.data.message
          };
        } else {
          return {
            success: false,
            message: response.data.detail || '更新密码失败'
          };
        }
      } catch (error) {
        console.error('更新密码请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.detail || '更新密码请求失败，请稍后再试'
        };
      }
    }
  },
  
  // 添加持久化配置
  persist: {
    enabled: true,
    strategies: [
      {
        key: 'user-store',
        storage: localStorage
      }
    ]
  }
});