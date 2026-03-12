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
    refreshToken: '',
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
        const response = await axios.post(`${apiConfig.userBaseURL}${apiConfig.endpoints.login}/`, {
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
          const userInfo = response.data.userInfo;
          // 存储access token作为JWT凭证
          const token = response.data.access || response.data.token;
          // 将token存入到localStorage
          localStorage.setItem('jwt_token', token);
          // console.log('存储token', token);
          // 存储refresh token用于后续刷新
          this.refreshToken = response.data.refresh;
          // 存储refresh token到localStorage
          localStorage.setItem('refresh_token', this.refreshToken);
          // console.log('存储refresh token', this.refreshToken);
          
          this.userInfo = userInfo;
          this.token = token;
          this.isLogin = true;
          
          return {
            success: true,
            message: '登录成功'
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
          message: error.response?.data?.detail || '登录请求失败，请稍后再试'
        };
      }
    },
    
    async login(userData) {
      try {
        // 发送登录请求
        const response = await axios.post(`${apiConfig.userBaseURL}${apiConfig.endpoints.login}/`, {
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
          const userInfo = response.data.userInfo;
          // 存储access token作为JWT凭证
          const token = response.data.access || response.data.token;
          // 存储refresh token用于后续刷新
          const refreshToken = response.data.refresh;
          
          // 将token存入到localStorage
          localStorage.setItem('jwt_token', token);
          console.log('存储token', token);
          // 存储refresh token到localStorage
          localStorage.setItem('refresh_token', refreshToken);
          console.log('存储refresh token', refreshToken);
          
          this.userInfo = userInfo;
          this.token = token;
          this.refreshToken = refreshToken;
          this.isLogin = true;
          
          return {
            success: true,
            message: '登录成功'
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
          message: error.response?.data?.detail || '登录请求失败，请稍后再试'
        };
      }
    },
    
    logout() {
      this.userInfo = null;
      this.token = '';
      this.refreshToken = '';
      this.isLogin = false;
      // 从localStorage中清除token
      localStorage.removeItem('jwt_token');
      localStorage.removeItem('refresh_token');
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
        const response = await axios.get(`${apiConfig.userBaseURL}${apiConfig.endpoints.profile}/`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-CSRFTOKEN': getCsrfToken()
          }
        });
        
        // 检查响应状态
        if (response.status === 200) {
          // 更新用户信息
          this.userInfo = response.data;
          
          return {
            success: true,
            message: '获取用户信息成功',
            data: response.data
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
    
    // 更新个人信息
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
        
        // 发送更新个人信息请求
        const response = await axios.put(`${apiConfig.userBaseURL}${apiConfig.endpoints.profile}/`, 
          userData,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              'X-CSRFTOKEN': getCsrfToken()
            }
          }
        );
        
        // 检查响应状态
        if (response.status === 200) {
          // 更新本地用户信息
          this.userInfo = { ...this.userInfo, ...userData };
          
          return {
            success: true,
            message: '更新个人信息成功'
          };
        } else {
          return {
            success: false,
            message: response.data.detail || '更新个人信息失败'
          };
        }
      } catch (error) {
        console.error('更新个人信息请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.detail || '更新个人信息请求失败，请稍后再试'
        };
      }
    },
    
    // 更新个人简介（保持向后兼容）
    async updateUserBio(bio) {
      return this.updateUserInfo({ bio });
    },
    
    // 修改密码
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
        
        // 发送修改密码请求
        const response = await axios.put(`${apiConfig.userBaseURL}${apiConfig.endpoints.profile}/`, 
          { 
            oldPassword,
            newPassword 
          },
          {
            headers: {
              Authorization: `Bearer ${token}`,
              'X-CSRFTOKEN': getCsrfToken()
            }
          }
        );
        
        // 检查响应状态
        if (response.status === 200) {
          return {
            success: true,
            message: '密码修改成功'
          };
        } else {
          return {
            success: false,
            message: response.data.detail || '密码修改失败'
          };
        }
      } catch (error) {
        console.error('修改密码请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.detail || '修改密码请求失败，请稍后再试'
        };
      }
    },
    
    // 刷新token
    async refreshToken() {
      try {
        // 从localStorage获取token和refreshToken
        const token = localStorage.getItem('jwt_token') || this.token;
        const refreshToken = localStorage.getItem('refresh_token') || this.refreshToken;
        // 检查是否有token
        if (!token || !refreshToken) {
          return {
            success: false,
            message: '未登录'
          };
        }
        
        // 发送刷新token请求
        const response = await axios.post(`${apiConfig.userBaseURL}${apiConfig.endpoints.refreshToken}/`, {
          refresh: refreshToken
        }, {
          headers: {
            'X-CSRFTOKEN': getCsrfToken()
          }
        });
        
        // 检查响应状态
        if (response.status === 200) {
          // 更新token
          const newToken = response.data.access || response.data.token;
          this.token = newToken;
          // 更新localStorage中的token
          localStorage.setItem('jwt_token', newToken);
          
          return {
            success: true,
            message: 'Token刷新成功'
          };
        } else {
          return {
            success: false,
            message: response.data.detail || 'Token刷新失败'
          };
        }
      } catch (error) {
        console.error('Token刷新请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.detail || 'Token刷新请求失败，请稍后再试'
        };
      }
    },
    
    // 注册
    async register(userData) {
      try {
        // 发送注册请求
        const response = await axios.post(`${apiConfig.userBaseURL}${apiConfig.endpoints.register}/`, {
          user_name: userData.username,
          email: userData.email,
          password: userData.password,
          password2: userData.confirmPassword,
          phone: userData.phone
        }, {
          headers: {
            'X-CSRFTOKEN': getCsrfToken()
          }
        });
        
        // 检查响应状态
        if (response.status === 201) {
          // 注册成功
          return {
            success: true,
            message: '注册成功'
          };
        } else {
          // 注册失败
          return {
            success: false,
            message: response.data.detail || '注册失败'
          };
        }
      } catch (error) {
        console.error('注册请求失败:', error);
        return {
          success: false,
          message: error.response?.data?.detail || '注册请求失败，请稍后再试'
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